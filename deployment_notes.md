Deployment notes and production considerations:

- Use HTTPS and a robust load balancer (Cloud Run, ECS, GKE, or Heroku)
- Use a managed database (Postgres) instead of SQLite for concurrency and reliability
- Replace background polling worker with a real queue system (Redis + RQ/Celery) for scale
- Implement observability: Prometheus metrics, structured logs and Sentry for errors
- Add RBAC/auth for admin routes and rate-limiting for webhook endpoints
- Use secret manager for API keys and rotate regularly
- Implement full webhook signature verification per provider docs (Shopify, Whop, Stripe, etc.)
