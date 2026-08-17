Xerin Task 8 - Wallet/Escrow Accounting Integration

Backend:
- verified completed payments already create commissions, seller pending credits and escrow holds
- escrow release now atomically moves seller wallet pending -> available
- platform commission is never credited to seller wallet
- customer can approve receipt only after all shipments are delivered and payment is completed
- customer approval releases all non-disputed order escrow holds
- repeated approval/release is idempotent
- admin escrow release uses the same wallet-safe release engine
- automatic release period uses the same escrow engine
- legacy fund release can no longer bypass active escrow
- no database migration required

New customer APIs:
GET  /api/v1/orders/{order_id}/escrow
POST /api/v1/orders/{order_id}/approve-receipt
