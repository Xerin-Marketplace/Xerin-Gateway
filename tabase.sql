psql "postgresql://postgres:new_password@localhost:5432/postgres"

\dt

SELECT * FROM users;

\x on
SELECT * FROM users ORDER BY created_at DESC;

#If many Rows 

SELECT id, first_name, last_name, email, phone, status, is_verified, created_at
FROM users
ORDER BY created_at DESC
LIMIT 100;

\q


| Phase  | Role/System               | Tasks |
| ------ | ------------------------- | ----: |
| **1**  | Seller                    |     7 |
| **2**  | Customer                  |     8 |
| **3**  | Logistics Company         |     9 |
| **4**  | Logistics Pricing Engine  |     7 |
| **5**  | Multi-Seller Fulfillment  |     6 |
| **6**  | Pickup Verification       |     7 |
| **7**  | Settlement & Wallet       |     8 |
| **8**  | Delivery Verification     |     5 |
| **9**  | Partner API & Security    |     7 |
| **10** | QA / Production Hardening |     8 |
