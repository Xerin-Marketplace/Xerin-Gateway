# Phase 1 — Multi-Store Backend Foundation

## What changed

- A seller can own multiple stores (`Seller.stores`).
- Removed the database/model one-store-per-seller uniqueness rule.
- Added `StoreScope`: `local` or `global`.
- Store scope is derived by the backend from `country`:
  - Tanzania -> `local`
  - any explicitly different country -> `global`
- Added `StoreCreate` schema.
- Added multi-store seller APIs while retaining the old `/stores/me` API temporarily for frontend compatibility.
- Updated wishlist legacy access from `Seller.store` to `Seller.stores`.
- Added Alembic migration `p39_multi_store_foundation`.

## New seller store APIs

- `GET /stores/mine` — list all stores belonging to current seller.
- `POST /stores` — create another store; `country` is required.
- `GET /stores/mine/{store_id}` — get one owned store.
- `PATCH /stores/mine/{store_id}` — update one owned store.
- `POST /stores/mine/{store_id}/logo` — update the selected store logo.
- `POST /stores/mine/{store_id}/banner` — update the selected store banner.

Existing `/stores/me`, `/stores/me/logo`, and `/stores/me/banner` are retained as compatibility endpoints and operate on the seller's oldest store. They can be retired after the Phase 2 frontend is migrated.

## Deployment

From your backend virtual environment:

```bash
alembic upgrade head
```

Confirm:

```bash
alembic current
```

Expected head:

```text
p39_multi_store_foundation (head)
```

Then restart the API and run your tests.

## Important Phase Boundary

Products still belong only to a seller in Phase 1. They are NOT assigned to a store yet. That is intentionally reserved for Phase 3, so current storefront product queries continue using `seller_id` until `products.store_id` is introduced.
