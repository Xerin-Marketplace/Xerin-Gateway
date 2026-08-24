# Xerin Seller My Stores - Add Store visibility fix

Updated files:
- src/components/Seller/Store/StoreSettings.tsx
- src/lib/api/endpoints/store.ts

Changes:
1. GET /stores/mine returning HTTP 404 with detail "Store not found" is treated as an empty store list (`[]`).
2. A seller with no stores now reaches the normal empty-state UI and sees both `Add Store` and `Create first store`.
3. If the store-list request fails for another reason, the page still keeps an `Add Store` / `Create Store` action visible and also provides a Retry button.
4. Store creation still uses POST /stores and the existing multi-store form.

After copying the files into the full frontend project, run:

    npx tsc --noEmit --pretty false
    npm run build

Then deploy/restart the frontend and hard-refresh the browser.
