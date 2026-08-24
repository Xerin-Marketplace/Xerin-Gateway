# Xerin Marketplace — Phase 3.1 Store Location Management

## What this phase fixes

1. Repairs the legacy PostgreSQL `ix_stores_seller_id` UNIQUE index so a seller can create multiple stores.
2. Adds a controlled country dropdown for the first supported markets:
   - Tanzania (LOCAL)
   - United Arab Emirates / Dubai (GLOBAL)
   - China (GLOBAL)
   - Turkey (GLOBAL)
   - United States (GLOBAL)
   - United Kingdom (GLOBAL)
3. Adds cascading searchable location inputs.
   - Tanzania: Region -> District/Municipality -> Ward -> Street
   - Global: State/Province/Emirate -> City -> Area/Neighborhood -> Street
4. Keeps the backend as the authority for LOCAL/GLOBAL store classification.
5. Keeps manual typing as a fallback if a place is missing or the public location-data service is temporarily unavailable.

## Updated files

- `backend/alembic/versions/p41_store_multistore_index_fix.py`
- `frontend/src/components/Seller/Store/StoreSettings.tsx`
- `frontend/src/lib/locations/storeLocations.ts`

## Backend deployment

Copy the backend migration into the same path in your backend and run:

```bash
cd /var/Xerin-Gateway/BACKEND
source .venv/bin/activate
alembic upgrade head
alembic current
```

Expected head after Phase 3.1:

```text
p41_store_multistore_index_fix (head)
```

Verify that `stores.seller_id` is no longer unique:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'stores'
  AND indexname = 'ix_stores_seller_id';
```

Expected form:

```text
CREATE INDEX ix_stores_seller_id ON public.stores USING btree (seller_id)
```

It must NOT contain `CREATE UNIQUE INDEX`.

Restart the API:

```bash
sudo systemctl restart xerin-api
sudo journalctl -u xerin-api -f
```

## Frontend deployment

Copy the two frontend files into the same paths in the full frontend project, then run:

```bash
npx tsc --noEmit --pretty false
npm run build
```

Deploy/restart the frontend and hard refresh the browser.

## Seller location flow

### Tanzania

```text
Country: Tanzania
  -> Region
  -> District / Municipality
  -> Ward
  -> Street / physical address
```

The store is shown as `LOCAL`.

### Global

```text
Country: UAE / China / Turkey / USA / UK
  -> State / Province / Emirate
  -> City
  -> Area / Neighborhood
  -> Street / physical address
```

The store is shown as `GLOBAL`.

## Location data behavior

Tanzania region/district/ward suggestions are fetched from the Tanzania GeoData API.
Global state/province/city suggestions are fetched from CountriesNow.
The inputs use searchable browser datalists and still permit manual typing as a production-safe fallback.

## Important

Phase 3.1 does not change `products.store_id`; that remains the Phase 3 product-store relationship. This phase improves store creation/location management and repairs the database uniqueness issue found in the server logs.
