# Phase 3 Task 13 — Wishlist & Favorite Stores

## Added routes

- `POST /api/v1/wishlist/products/{product_id}`
- `DELETE /api/v1/wishlist/products/{product_id}`
- `GET /api/v1/wishlist/products`
- `POST /api/v1/wishlist/stores/{store_slug}`
- `DELETE /api/v1/wishlist/stores/{store_slug}`
- `GET /api/v1/wishlist/stores`
- `GET /api/v1/wishlist/summary`
- `DELETE /api/v1/wishlist/clear`

## Installation

Copy the patch contents into the backend root, then run:

```bash
alembic upgrade head
python -m api.seed_permissions
python -m pytest tests/test_phase3_task13_wishlist.py -v
python -m pytest -m "not integration" -v
```

# GIT 

git reset --hard origin/main
git pull origin main

J3W2q5srfbxd

b53aL4j0#
