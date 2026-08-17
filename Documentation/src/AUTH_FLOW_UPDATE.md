# Authentication flow

## Customer
`/signin` -> Sign Up -> POST `/auth/register` -> OTP is sent -> `/verify-otp?phone=...&email=...&purpose=register` -> Verify -> `/signin`

## Seller
`/signin` -> Seller -> POST `/auth/register-seller` -> OTP is sent -> `/verify-otp?phone=...&email=...&purpose=register_seller` -> Verify -> `/signin`

The OTP page never asks the user to re-enter a phone number. The registration phone is transferred through the verification URL and is only displayed in masked form.

`/verify-otp` is now treated as an authentication page, so the storefront Header/Footer are hidden.

The registration components use the submitted email/phone as fallback values when building the OTP URL, preventing `phone=undefined` and `email=undefined`.
