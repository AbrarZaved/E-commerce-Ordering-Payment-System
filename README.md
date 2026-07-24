# E-commerce Ordering & Payment System (Backend)

A Django + Django REST Framework backend for an e-commerce ordering and payment
system. Built for a take-home assessment: emphasis on clean architecture, the
**Strategy pattern** for pluggable payments (Stripe + bKash), a **DFS + Redis**
category-tree recommendation engine, and safe, concurrent stock handling.

---

## Tech stack
- Django + DRF
- PostgreSQL
- Redis (category-tree cache + Celery broker)
- Celery (async webhook processing, emails)
- JWT auth (SimpleJWT)
- drf-spectacular (OpenAPI/Swagger)
- Docker + docker-compose

## Project layout
```
config/            settings.py (single, env-driven), urls, celery
apps/
  core/            base models, exceptions, pagination, permissions
  users/           custom email User, registration, JWT login
  products/        Product, Category tree, DFS + Redis cache, recommendations
  orders/          Order, OrderItem, deterministic total calculation
  payments/
    strategies/    PaymentStrategy ABC + StripeStrategy + BkashStrategy + registry
    webhooks/      provider webhook endpoints
    service.py     PaymentService (runtime strategy selection, no branching)
docs/              ERD, architecture, payment sequence diagrams (Mermaid)
seeders/           management commands: seed_admin, seed_products
tests/             unit + API + webhook tests
```
> Django management commands must live inside an app, so the `seeders/` folder
> is a tiny app exposing `seed_admin` and `seed_products`.

---

## Quick start (Docker)
```bash
cp .env.example .env          # fill in Stripe/bKash test creds
docker compose up --build
```
This starts Postgres, Redis, the web app, and a Celery worker. On boot the web
container runs migrations and seeds an admin + sample products.

- API root: http://localhost:8000/api/v1/
- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/
- Admin: http://localhost:8000/admin/ (`admin@example.com` / `admin12345`)

## Quick start (local, no Docker)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Use SQLite/locmem quickly, or point DATABASE_URL/REDIS_URL at local services
export DATABASE_URL=sqlite:///db.sqlite3 USE_LOCMEM_CACHE=True CELERY_TASK_ALWAYS_EAGER=True
python manage.py makemigrations users products cart orders payments
python manage.py migrate
python manage.py seed_admin && python manage.py seed_products
python manage.py runserver
```

## Running tests
```bash
pytest
```
Covers: order total & subtotal calc, stock reduction, DFS traversal &
recommendations, category-tree structure, auth + ownership scoping, order
creation, full checkout flow, and Stripe/bKash webhook handling.

---

## Environment variables
See `.env.example` for the full list. Highlights:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret |
| `DATABASE_URL` | Postgres DSN |
| `REDIS_URL` | cache + Celery broker |
| `CELERY_TASK_ALWAYS_EAGER` | run tasks inline (no worker) for local dev |
| `STRIPE_API_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe test-mode creds |
| `BKASH_APP_KEY` / `BKASH_APP_SECRET` / `BKASH_USERNAME` / `BKASH_PASSWORD` | bKash sandbox creds |

**Secrets are read from environment variables only and never committed.**

---

## API summary
All app endpoints are under `/api/v1/`.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register/` | public | Register (email + password) |
| POST | `/auth/login/` | public | JWT login -> access/refresh |
| POST | `/token/refresh/` | public | Refresh access token |
| GET | `/auth/me/` | user | Current user |
| GET/POST | `/products/` | list public / write admin | Products (filter, search, paginate) |
| GET | `/products/{id}/recommendations/` | public | DFS-based related products |
| GET/POST | `/categories/` | list public / write admin | Categories |
| GET | `/categories/tree/` | public | Cached nested tree |
| GET/POST | `/orders/` | user | List/create own orders |
| POST | `/payments/initiate/` | user | Start payment for a pending order |
| POST | `/payments/confirm/` | user | Execute/confirm a payment |
| GET | `/payments/{id}/verify/` | user | Query provider status |
| POST | `/webhooks/stripe/` | provider | Stripe webhook (signature-verified) |
| POST | `/webhooks/bkash/` | provider | bKash webhook (signature-verified) |

### Order flow
1. User creates an order from products (`status=pending`).
2. User picks a provider and calls `/payments/initiate/`.
3. `PaymentService` selects the strategy and initiates payment.
4. Provider confirms via webhook (Stripe) or execute/poll (bKash).
5. Order status updates; **stock is reduced only after payment success**.

---

## Webhook testing with ngrok
Providers need a public URL to reach your local webhook endpoints:
```bash
ngrok http 8000
# Stripe: set webhook to https://<id>.ngrok.io/webhooks/stripe/
#         stripe listen --forward-to localhost:8000/webhooks/stripe/
# bKash:  configure sandbox callback/webhook to https://<id>.ngrok.io/webhooks/bkash/
```
Put the resulting signing secret in `STRIPE_WEBHOOK_SECRET` / `BKASH_WEBHOOK_SECRET`.

---

## Design decisions

### Custom User model
We extend `AbstractBaseUser + PermissionsMixin` (not the default `User`, not
`AbstractUser`) because the spec requires **email-only** auth with no username.
This keeps the identity model minimal and avoids carrying an unused `username`
field, while a custom `UserManager` provides `create_user`/`create_superuser`.

### Strategy pattern (the real test)
`PaymentStrategy` (ABC) defines `initiate / confirm / verify / parse_webhook`.
`StripeStrategy` and `BkashStrategy` implement it. `PaymentService` looks the
strategy up in a registry by `provider` string and calls the interface only —
there is **no provider-specific branching** in orders or payment orchestration.
Adding a third provider (e.g. PayPal) means: write `PaypalStrategy`, add one
line to the registry. `tests/test_payment_strategy.py` proves this.

### DFS + Redis caching
Categories form a self-referential tree. `dfs_descendant_category_ids` does an
explicit-stack depth-first traversal to collect a category subtree; the built
tree is cached in Redis with a TTL and invalidated on any category write via
Django signals. `/products/{id}/recommendations/` surfaces active, in-stock
products from the product's category subtree, ranked by DFS proximity.

### Concurrency-safe stock
`reduce_stock_for_order` locks each product row with `select_for_update()`
inside an atomic transaction, so concurrent orders can't oversell. Stock is only
reduced once a payment succeeds, and the paid transition is idempotent.

### Consistent errors
A custom DRF exception handler wraps all errors in
`{"error": {"code", "message", "details"}}`. Domain errors
(`InsufficientStockError`, `PaymentError`, `InvalidOrderState`) map to correct
HTTP status codes.

---

## Assumptions made
- JWT (stateless) over session auth, since this is an API-only backend.
- Payment `initiate` records intent; **for Stripe, success is confirmed via
  webhook**; for bKash the client triggers `confirm` (execute) then optional
  webhook. Both paths converge on the same idempotent state transition.
- bKash amounts are treated as BDT; Stripe uses `STRIPE_CURRENCY` (default USD).
- Migrations are generated on first boot (`makemigrations`) to keep the repo
  clean; in a real project they would be committed.
