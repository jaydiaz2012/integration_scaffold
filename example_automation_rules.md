Example automation rules (implement these in your visual/no-code engine or directly as code):

1) Welcome & Onboarding
Trigger: order_paid or subscription_created
Action sequence:
  - Grant entitlement (platform sync)
  - Send welcome email (via email provider)
  - Assign Discord role
  - Start 7-day drip onboarding (series of messages + content unlocks)

2) Failed payment dunning
Trigger: invoice.payment_failed
Action sequence:
  - Mark account as past_due in analytics
  - Send payment retry emails at 1, 3, 7 days
  - After 7 days without success -> revoke entitlement and issue cancellation message

3) Refund handling
Trigger: refund.created or charge.refunded
Action sequence:
  - Revoke entitlement immediately
  - Create refund via payments adapter (idempotent)
  - Notify support with stitch of last 10 events for the user

4) Upsell funnel
Trigger: user reached module X and is on plan A
Action sequence:
  - Send targeted upsell offer
  - If accepted -> grant upgraded entitlement + prorate billing via payments adapter
