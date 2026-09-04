# Billing (Phase 21)

Plans are listed via `/api/v1/billing/list-plans`. Quota enforcement continues to use `users.bytes_limit`.

Stripe Customer Portal is stubbed until `STRIPE_SECRET_KEY` (and price IDs) are set. Then replace `create_billing_portal` with a real Stripe Billing Portal session.
