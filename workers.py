# workers.py
# Updated to allow direct invocation from event webhooks
# Synchronous Discord adapter, 10-tier membership logic, temporary access handling

from datetime import datetime, timedelta
from threading import Thread
import queue

from models import AutomationRule, UserTier, EventLog
from adapters import DiscordAdapter
from utils import logger, with_idempotency

# Worker queue
task_queue = queue.Queue()

discord = DiscordAdapter()


def enqueue_task(task):
    task_queue.put(task)


def worker_loop():
    while True:
        task = task_queue.get()
        if task is None:
            break
        try:
            process_task(task)
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            task_queue.task_done()


worker_thread = Thread(target=worker_loop, daemon=True)
worker_thread.start()


@with_idempotency
def process_task(task):
    event_type = task.get("event_type")
    user_id = task.get("user_id")
    tiers = task.get("tiers", [])
    guild_id = task.get("guild_id")
    timestamp = datetime.utcnow()

    EventLog.create(event_type=event_type, user_id=user_id, payload=task)

    if event_type == "purchase":
        handle_purchase(user_id, tiers, guild_id, timestamp)

    elif event_type == "cancel":
        handle_cancel(user_id, tiers, guild_id)

    elif event_type == "renewal":
        handle_renewal(user_id, tiers, guild_id)


###############################################
# HANDLERS
###############################################

def handle_purchase(user_id, tiers, guild_id, timestamp):
    for tier in tiers:
        UserTier.grant(user_id, tier)

        role_id = discord.get_role_for_tier(guild_id, tier)
        if role_id:
            discord.assign_role(guild_id, user_id, role_id)

    # Temporary access logic: apply Tier 1 for +5 days
    temporary_until = timestamp + timedelta(days=5)
    UserTier.grant(user_id, "temporary_tier_1", expires_at=temporary_until)

    temp_role = discord.get_role_for_tier(guild_id, "temporary_tier_1")
    if temp_role:
        discord.assign_role(guild_id, user_id, temp_role)

    logger.info(f"Purchase handled for {user_id} in guild {guild_id}")


def handle_cancel(user_id, tiers, guild_id):
    for tier in tiers:
        UserTier.revoke(user_id, tier)

        role_id = discord.get_role_for_tier(guild_id, tier)
        if role_id:
            discord.remove_role(guild_id, user_id, role_id)

    logger.info(f"Cancel handled for {user_id} in guild {guild_id}")


def handle_renewal(user_id, tiers, guild_id):
    for tier in tiers:
        UserTier.extend(user_id, tier, days=30)

    logger.info(f"Renewal handled for {user_id} in guild {guild_id}")

