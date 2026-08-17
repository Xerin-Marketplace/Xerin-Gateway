# Pending Seller Activation Flow

A seller whose `seller_status` is not `approved` is treated as an activation-stage seller.

Available navigation:
- Dashboard
- KYC Verification
- Business Documents
- Account Settings
- Security
- Help & Support

Restricted until approval:
- Products / Add Product
- Inventory
- Orders / Returns / Cancellations
- Store Profile / Promotions / Reviews / Messages
- Earnings / Payouts / Transactions

Implementation:
- `SellerLayout.tsx` switches the sidebar based on live seller status from `GET sellers/me`.
- Direct navigation to restricted seller URLs redirects a pending seller to `/seller/dashboard`.
- The dashboard loads seller/KYC/document/profile data first. Commerce APIs are only called when status is `approved`.
- Pending sellers see an activation dashboard rather than commerce metrics.
- `Business Documents` has a dedicated route at `/seller/documents`.
- After the backend changes seller status to `approved`, the full Seller Center menu and commerce dashboard become available automatically after refresh/re-login.
