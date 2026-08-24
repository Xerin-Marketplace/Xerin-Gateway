# Xerin Phase 3 — Product → Store Assignment

## Result
Every product now belongs to exactly one seller-owned store.

## Backend changes
- `products.store_id` added as a mandatory FK to `stores.id`.
- Existing products are backfilled to the seller's earliest store (the old one-store-per-seller store).
- Migration stops with a clear error if an existing product belongs to a seller with no store.
- `ProductCreate.store_id` is mandatory.
- `ProductUpdate.store_id` supports moving an editable product between the seller's own stores.
- Create/update reject a store owned by another seller.
- `GET /products?store_id=...` filters public products by store.
- `GET /products/my-products?store_id=...` filters the current seller's products by store and validates ownership.
- Public storefront product/category queries now use `Product.store_id`, not `Product.seller_id`.

## Frontend changes
- Product API types now include `store_id`.
- Seller Product editor requires a Store selection.
- If the seller has one store it is preselected for new products.
- If the seller has no stores, Add Product is disabled and the UI directs them to My Stores.
- Product cards display the assigned store and LOCAL/GLOBAL scope.
- Products can be filtered by store from the seller catalogue.

## Apply backend
Copy the `backend/` files into the matching backend project paths, then run:

```bash
alembic upgrade head
alembic current
```

Expected head:

```text
p40_product_store_assignment (head)
```

Then restart the API, for example:

```bash
sudo systemctl restart xerin-api
sudo journalctl -u xerin-api -f
```

## Important migration pre-check
If you want to verify that every seller with products already has at least one store before migrating:

```sql
SELECT p.seller_id, COUNT(*) AS product_count
FROM products p
LEFT JOIN stores s ON s.seller_id = p.seller_id
WHERE s.id IS NULL
GROUP BY p.seller_id;
```

This should return zero rows. If it returns rows, create at least one store for those sellers first.

## Verify after migration

```sql
SELECT COUNT(*) AS products_without_store
FROM products
WHERE store_id IS NULL;
```

Expected: `0`.

Check product/store ownership consistency:

```sql
SELECT p.id AS product_id, p.seller_id AS product_seller, p.store_id,
       s.seller_id AS store_seller, s.store_name
FROM products p
JOIN stores s ON s.id = p.store_id
WHERE p.seller_id <> s.seller_id;
```

Expected: zero rows.

## Apply frontend
Copy the `frontend/` files into matching paths and run in the full frontend project:

```bash
npx tsc --noEmit --pretty false
npm run build
```

## Phase boundary
This phase assigns products to stores and updates storefront filtering. Store-aware shipment grouping, delivery pricing, pickup origins, checkout, and fulfillment remain Phase 4.
