# Adapter interfaces and placeholder implementations.
# Replace placeholders with real API calls and robust error handling.
import time
import httpx
from utils import get_env

class BaseAdapter:
    def __init__(self):
        self.http = httpx.Client(timeout=10.0)

class ShopifyAdapter(BaseAdapter):
    def __init__(self):
        super().__init__()
        self.api_key = get_env("SHOPIFY_API_KEY")
        self.api_secret = get_env("SHOPIFY_API_SECRET")
        # In production use OAuth or private app credentials and the shop domain.

    def verify_webhook(self, payload_bytes, signature_header):
        # Shopify uses HMAC SHA256 with the API secret and base64 signature.
        # Placeholder: implement actual verification for production.
        return True

    def reconcile_subscription(self, shop_customer_id):
        # Placeholder: fetch subscriptions and payment status from Shopify Admin API
        print("Reconciling subscription for shop_customer_id", shop_customer_id)
        return {"status": "active"}

class WhopAdapter(BaseAdapter):
    def __init__(self):
        super().__init__()
        self.api_key = get_env("WHOP_API_KEY")

    def verify_webhook(self, payload_bytes, signature_header):
        # Implement Whop webhook verification as per their docs.
        return True

    def get_user(self, whop_user_id):
        # Placeholder for fetching user details
        return {"id": whop_user_id, "email": f"user+{whop_user_id}@example.com"}

class DiscordAdapter(BaseAdapter):
    def __init__(self):
        super().__init__()
        self.token = get_env("DISCORD_BOT_TOKEN")
        self.api_base = "https://discord.com/api"

    def assign_role(self, guild_id, user_discord_id, role_id):
        url = f"{self.api_base}/guilds/{guild_id}/members/{user_discord_id}/roles/{role_id}"
        headers = {"Authorization": f"Bot {self.token}"}
        r = self.http.put(url, headers=headers)
        if r.status_code in (204, 200):
            return True
        else:
            r.raise_for_status()

    def remove_role(self, guild_id, user_discord_id, role_id):
        url = f"{self.api_base}/guilds/{guild_id}/members/{user_discord_id}/roles/{role_id}"
        headers = {"Authorization": f"Bot {self.token}"}
        r = self.http.delete(url, headers=headers)
        if r.status_code in (204, 200):
            return True
        else:
            r.raise_for_status()

class PaymentsAdapter(BaseAdapter):
    def __init__(self):
        super().__init__()

    def verify_webhook(self, payload_bytes, signature_header, secret):
        # Generic wrapper
        return True

    def create_refund(self, charge_id, amount):
        # Placeholder
        print("Creating refund for", charge_id, amount)
        return {"status": "succeeded"}
