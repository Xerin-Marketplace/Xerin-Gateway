Xerin x AzamPay - Task 6
RSA Callback Signature Verification

Implemented according to AzamPay Tanzania Checkout documentation:
- Fetches GET /azampay/v1/public-key?format=Pem using normal AzamPay auth.
- Caches PEM key for 24 hours by default.
- Signed data: utilityref + externalreference + transactionstatus + operator.
- Base64-decodes signature.
- Verifies RSA SHA-256 with PKCS#1 v1.5 padding.
- If verification fails, force-refreshes the public key and retries exactly once.
- Missing or invalid signatures are rejected BEFORE payment/order state changes.
- Verified callback audit metadata stores signature_verified=true but never stores
  the signature itself or callback password.

Config defaults:
AZAMPAY_PUBLIC_KEY_PATH=/azampay/v1/public-key?format=Pem
AZAMPAY_PUBLIC_KEY_CACHE_SECONDS=86400

Frontend changes: none.
Database migration: none.
