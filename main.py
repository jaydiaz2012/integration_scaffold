from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from models import init_db, get_engine, get_sessionmaker, Event, Task
from utils import get_env, verify_signature, register_idempotency
from adapters import ShopifyAdapter, WhopAdapter, DiscordAdapter, PaymentsAdapter
from workers import Worker
from sqlalchemy.orm import Session
from datetime import datetime
import json
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./integration.db")
SessionLocal = init_db(DATABASE_URL)

app = FastAPI(title="Integration Blueprint")

shopify = ShopifyAdapter()
whop = WhopAdapter()
discord = DiscordAdapter()
payments = PaymentsAdapter()

# start background worker thread when app starts
worker = Worker(SessionLocal, poll_interval=1)
worker.start()

def enqueue_task(session: Session, type_: str, payload: dict, run_after=None):
    t = Task(type=type_, payload=payload)
    if run_after:
        t.run_after = run_after
    session.add(t)
    session.commit()
    return t.id

@app.post("/webhook/shopify")
async def webhook_shopify(request: Request, x_shopify_hmac_sha256: str = Header(None)):
    body = await request.body()
    # verify signature (placeholder)
    if not shopify.verify_webhook(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=400, detail="Invalid signature")
    payload = await request.json()
    idempotency_key = payload.get("idempotency_key") or payload.get("id")
    session = SessionLocal()
    try:
        if not register_idempotency(session, idempotency_key):
            return {"status": "duplicate"}
        # Simplified: map event types from Shopify to internal tasks
        event_type = payload.get("type") or payload.get("topic") or payload.get("event")
        if event_type in ("subscription_created", "subscription_updated", "checkout_completed", "order_paid"):
            # grant entitlement
            enqueue_task(session, "grant_entitlement", {
                "user_external_id": payload.get("customer_id") or payload.get("customer", {}).get("id"),
                "product_code": payload.get("product_code") or payload.get("line_items", [{}])[0].get("sku"),
                "platform": "shopify",
                "email": (payload.get("customer", {}) or {}).get("email"),
                "discord": payload.get("discord")  # a webhook payload could include discord assignment hints
            })
        if event_type in ("subscription_cancelled", "subscription_ended"):
            enqueue_task(session, "revoke_entitlement", {
                "user_external_id": payload.get("customer_id") or payload.get("customer", {}).get("id"),
                "product_code": payload.get("product_code") or payload.get("line_items", [{}])[0].get("sku"),
                "platform": "shopify",
                "discord": payload.get("discord")
            })
        # ingest event for analytics
        enqueue_task(session, "ingest_event", {"platform": "shopify", "event_type": event_type, "payload": payload, "idempotency_key": idempotency_key})
        return {"status": "ok"}
    finally:
        session.close()

@app.post("/webhook/whop")
async def webhook_whop(request: Request, x_whop_signature: str = Header(None)):
    body = await request.body()
    if not whop.verify_webhook(body, x_whop_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
    payload = await request.json()
    idempotency_key = payload.get("idempotency_key") or payload.get("id")
    session = SessionLocal()
    try:
        if not register_idempotency(session, idempotency_key):
            return {"status": "duplicate"}
        event_type = payload.get("event") or payload.get("type")
        if event_type in ("purchase", "order.created", "subscription.created"):
            enqueue_task(session, "grant_entitlement", {
                "user_external_id": payload.get("user_id"),
                "product_code": payload.get("product_handle") or payload.get("product_id"),
                "platform": "whop",
                "email": payload.get("email"),
                "discord": payload.get("discord")
            })
        if event_type in ("subscription.cancelled", "order.refunded"):
            enqueue_task(session, "revoke_entitlement", {
                "user_external_id": payload.get("user_id"),
                "product_code": payload.get("product_handle") or payload.get("product_id"),
                "platform": "whop",
                "discord": payload.get("discord")
            })
        enqueue_task(session, "ingest_event", {"platform": "whop", "event_type": event_type, "payload": payload, "idempotency_key": idempotency_key})
        return {"status": "ok"}
    finally:
        session.close()

@app.post("/webhook/payments")
async def webhook_payments(request: Request, x_signature: str = Header(None)):
    body = await request.body()
    # verify payment provider signature using configured secret
    if not payments.verify_webhook(body, x_signature, get_env("PAYMENTS_WEBHOOK_SECRET")):
        raise HTTPException(status_code=400, detail="Invalid signature")
    payload = await request.json()
    idempotency_key = payload.get("idempotency_key") or payload.get("id")
    session = SessionLocal()
    try:
        if not register_idempotency(session, idempotency_key):
            return {"status": "duplicate"}
        event_type = payload.get("type") or payload.get("event")
        # basic mapping
        if event_type in ("charge.refunded", "refund.created"):
            enqueue_task(session, "create_refund", {"charge_id": payload.get("charge_id"), "amount": payload.get("amount")})
        if event_type in ("invoice.payment_failed", "charge.failed"):
            # schedule retry / dunning flow
            enqueue_task(session, "reconcile_billing", {"shop_customer_id": payload.get("customer_id")})
        enqueue_task(session, "ingest_event", {"platform": "payments", "event_type": event_type, "payload": payload, "idempotency_key": idempotency_key})
        return {"status": "ok"}
    finally:
        session.close()

@app.post("/admin/run_reconcile")
async def admin_run_reconcile(background_tasks: BackgroundTasks):
    session = SessionLocal()
    # enqueue a reconciliation task for all active users (simplified)
    background_tasks.add_task(run_reconcile_all, )
    return {"status": "scheduled"}

def run_reconcile_all():
    session = SessionLocal()
    # In production, paginate and handle large sets; here is a simplified example
    from models import User
    users = session.query(User).all()
    for u in users:
        enqueue_task(session, "reconcile_billing", {"shop_customer_id": u.external_id})
    session.close()

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
