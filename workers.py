# workers.py

import time
from typing import Dict, Any, List
from adapters import DiscordAdapter


class EntitlementWorker:
    """
    Handles:
      - New purchase access
      - Tier upgrades/downgrades
      - Expiry enforcement
      - Multi-guild distribution
      - Discord invite generation
      - Event logging

    This worker is intentionally synchronous so it can run inside
    a background process, cron, or webhook handler.
    """

    def __init__(
        self,
        discord_adapter: DiscordAdapter,
        managed_guilds: List[str],
        logger=None
    ):
        self.discord = discord_adapter
        self.managed_guilds = managed_guilds
        self.logger = logger or print  # simple default logger

    # -------------------------------------------------------------
    # MAIN ENTRY POINT
    # -------------------------------------------------------------
    def process_entitlement(
        self,
        user_id: str,
        tier_name: str,
        temporary: bool = True
    ) -> Dict[str, Any]:
        """
        Applies the correct tier across ALL managed guilds.
        Calls expiry cleanup before reassigning.
        """

        overall = {
            "user_id": user_id,
            "tier": tier_name,
            "guild_results": {}
        }

        for guild_id in self.managed_guilds:

            self.logger(f"[EntitlementWorker] Processing {user_id} in guild {guild_id}")

            # --- Step 1: enforce expiry before anything else ---
            expired_removed = self.discord.enforce_expiry(guild_id, user_id)

            # --- Step 2: assign tier (adds new, removes old) ---
            tier_result = self.discord.assign_tier(
                guild_id=guild_id,
                user_id=user_id,
                tier_name=tier_name,
                temporary=temporary
            )

            # --- Step 3: generate invite only if user not in guild ---
            invite_url = None
            if not self.discord.is_member(guild_id, user_id):
                # You may want to define a welcome channel mapping per guild
                welcome_channel = self._default_welcome_channel(guild_id)
                invite_url = self.discord.create_invite(
                    channel_id=welcome_channel,
                    max_uses=1,
                    expires_in_seconds=3600
                )
                self.logger(f"[EntitlementWorker] Created invite for {user_id}: {invite_url}")

            # store per-guild results
            overall["guild_results"][guild_id] = {
                "expired_removed": expired_removed,
                "tier_assignment": tier_result,
                "invite": invite_url
            }

        return overall

    # -------------------------------------------------------------
    # EXTERNAL SCHEDULED CLEANUP (for auto-expiry)
    # -------------------------------------------------------------
    def cleanup_expired_access(self) -> Dict[str, Any]:
        """
        Iterates through all guilds + all expiry keys inside
        the discord adapter storage and removes expired roles.

        Ideal for a CRON job: runs every 10
