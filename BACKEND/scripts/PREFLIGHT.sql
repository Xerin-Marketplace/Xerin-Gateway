-- Run these checks before `alembic upgrade head`.

-- Duplicate inventory rows for the same variant (must return zero rows).
SELECT product_id, variant_id, COUNT(*)
FROM inventory
WHERE variant_id IS NOT NULL
GROUP BY product_id, variant_id
HAVING COUNT(*) > 1;

-- Duplicate product-level inventory rows (variant_id is NULL; must return zero rows).
SELECT product_id, COUNT(*)
FROM inventory
WHERE variant_id IS NULL
GROUP BY product_id
HAVING COUNT(*) > 1;

-- Duplicate payment provider transaction IDs (must return zero rows).
SELECT provider_transaction_id, COUNT(*)
FROM payments
WHERE provider_transaction_id IS NOT NULL
GROUP BY provider_transaction_id
HAVING COUNT(*) > 1;

-- Products that violate the new price rules (must return zero rows).
SELECT id, price, sale_price
FROM products
WHERE price < 0 OR sale_price < 0 OR sale_price > price;

-- Payments with negative amounts (must return zero rows).
SELECT id, amount FROM payments WHERE amount < 0;
