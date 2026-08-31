CUSTOMER PAYMENT
       │
       ├── Seller entitlement → ESCROW / HELD
       └── Logistics fee      → PENDING
                    ↓
             Seller prepares
                    ↓
             Seller handover
                    ↓
              Pickup proof
                    ↓
        Pickup = custody evidence only
        ❌ Seller money is NOT released
                    ↓
             Product delivered
                    ↓
       Recipient OTP + GPS verification
                    ↓
           VERIFIED DELIVERY
             ┌──────┴───────┐
             │              │
             ▼              ▼
        LOGISTICS       SELLER ESCROW
        AVAILABLE       remains HELD
                             │
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
        Customer accepts  Customer silent  Customer reports
               │             │             │
               ▼             ▼             ▼
        Release seller   Wait Admin X days Structured claim
                             │             │
                             ▼        classify responsibility
                      No eligible claim    │
                             │      ┌──────┼────────┐
                             ▼      ▼      ▼        ▼
                          RELEASE Seller Logistics Customer
                                  │      │        │
                              Hold item No seller No seller
                                        hold      hold