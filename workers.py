# Background worker that picks pending tasks and runs them with retry and idempotency logic.
import threading
import time
from datetime import datetime, timedelta
from models import Task, Event, Entitlement, User
from sqlalchemy.orm import Session
from adapters import ShopifyAdapter, WhopAdapter, DiscordAdapter, PaymentsAdapter
from utils import register_idempotency

shopify = ShopifyAdapter()
whop = WhopAdapter()
discord = DiscordAdapter()
payments = PaymentsAdapter()

class Worker(threading.Thread):
    def __init__(self, SessionLocal, poll_interval=5):
        super().__init__(daemon=True)
        self.SessionLocal = SessionLocal
        self.poll_interval = poll_interval
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        while not self._stop:
            session = self.SessionLocal()
            try:
                now = datetime.utcnow()
                task = session.query(Task)                    .filter(Task.state=="pending")                    .filter(Task.run_after <= now)                    .order_by(Task.created_at)                    .first()
                if not task:
                    session.close()
                    time.sleep(self.poll_interval)
                    continue

                task.state = "in_progress"
                session.commit()

                success = self.handle_task(session, task)
                if success:
                    task.state = "done"
                    task.attempts += 1
                    session.commit()
                else:
                    task.attempts += 1
                    task.last_error = "failed attempt"
                    if task.attempts >= task.max_attempts:
                        task.state = "failed"
                    else:
                        task.state = "pending"
                        task.run_after = datetime.utcnow() + timedelta(seconds=2 ** task.attempts)
                    session.commit()

            except Exception as e:
                print("Worker exception:", e)
            finally:
                session.close()
            time.sleep(self.poll_interval)

    def handle_task(self, session: Session, task: Task):
        try:
            payload = task.payload or {}
            t = task.type
            if t == "grant_entitlement":
                # idempotency: ensure single grant per key
                key = payload.get("idempotency_key") or f"grant:{payload.get('user_external_id')}:{payload.get('product_code')}"
                if not register_idempotency(session, key):
                    print("Idempotency prevented duplicate grant", key)
                    return True
                # create or reactivate entitlement
                user = session.query(User).filter_by(external_id=payload.get("user_external_id")).first()
                if not user:
                    user = User(external_id=payload.get("user_external_id"), email=payload.get("email"))
                    session.add(user)
                    session.commit()
                ent = session.query(Entitlement).filter_by(user_id=user.id, product_code=payload.get("product_code")).first()
                if ent and ent.active:
                    print("Entitlement already active")
                    return True
                if ent and not ent.active:
                    ent.active = True
                    ent.granted_at = datetime.utcnow()
                    ent.revoked_at = None
                else:
                    ent = Entitlement(user_id=user.id, product_code=payload.get("product_code"), platform=payload.get("platform"))
                    session.add(ent)
                session.commit()
                # example: assign discord role if discord info provided
                if payload.get("discord"):
                    discord.assign_role(payload["discord"]["guild_id"], payload["discord"]["user_id"], payload["discord"]["role_id"])
                return True

            if t == "revoke_entitlement":
                user = session.query(User).filter_by(external_id=payload.get("user_external_id")).first()
                if not user:
                    return True
                ent = session.query(Entitlement).filter_by(user_id=user.id, product_code=payload.get("product_code")).first()
                if not ent or not ent.active:
                    return True
                ent.active = False
                ent.revoked_at = datetime.utcnow()
                session.commit()
                if payload.get("discord"):
                    discord.remove_role(payload["discord"]["guild_id"], payload["discord"]["user_id"], payload["discord"]["role_id"])
                return True

            if t == "reconcile_billing":
                # call Shopify adapter or payments adapter to reconcile subscriptions
                result = shopify.reconcile_subscription(payload.get("shop_customer_id"))
                print("Reconciliation result", result)
                return True

            if t == "create_refund":
                result = payments.create_refund(payload.get("charge_id"), payload.get("amount"))
                return True

            # default: store event for analytics
            if t == "ingest_event":
                ev = Event(platform=payload.get("platform"), event_type=payload.get("event_type"), payload=payload, idempotency_key=payload.get("idempotency_key"))
                session.add(ev)
                session.commit()
                return True

            return True

        except Exception as e:
            print("Task processing error:", e)
            return False
