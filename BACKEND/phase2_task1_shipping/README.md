# Phase Two — Task 1: Addresses and Shipping Configuration

This package adds production-oriented customer addresses, shipping zones, methods, rates, and quote calculation. It does not yet create shipments or connect a selected shipping rate to order checkout; that is Task 2.3.

## Install
Back up and replace the included `api` files. Copy `alembic/versions/phase2_task1_shipping.py` into your project.

Before running migration:
1. `python -m alembic heads`
2. Replace `DOWN_REVISION` in the migration with the returned revision ID.
3. Inspect with `python -m alembic history --verbose`.
4. Run `python -m alembic upgrade head`.
5. Run `python -m api.seed_permissions`.
6. Run `python -m compileall api`.
7. Run `python -m pytest -m "not integration" -v`.

## New endpoints
- Existing `/api/v1/addresses` CRUD is expanded.
- `POST /api/v1/addresses/{id}/default`
- `POST/GET/PATCH /api/v1/shipping/zones`
- `POST/GET /api/v1/shipping/methods`
- `POST/GET /api/v1/shipping/rates`
- `POST /api/v1/shipping/quote`

## Important
Backfill any old address rows with null country/region/city/street before migration if needed.
