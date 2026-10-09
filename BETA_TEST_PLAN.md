# Xerin Marketplace — Beta Test Plan

End-to-end verification checklist for the beta launch. Run every flow on the
staging/production environment with **real** Selcom test
numbers before inviting layman testers.

Legend: ✅ pass · ❌ fail · ⚠️ pass with issues (record details)

---

## 0. Pre-flight environment checks

| Check | Command / Location | Expected |
|---|---|---|
| API healthy | `curl -s https://api.xerinmarketplace.com/health/live` | `200` |
| Storefront loads | `https://xerinmarketplace.com` | `200`, shows "Xerin Marketplace" |
| SMTP works | send_email test via `.venv/bin/python` (see ops runbook) | Test mail arrives |
| SMS works | send_sms test via `.venv/bin/python` | SMS arrives on test phone |
| Selcom configured | `.env` has `SELCOM_*` + callback URL `https://api.xerinmarketplace.com/api/v1/payments/selcom/callback` | Keys present |
| KYC notification templates seeded | `SELECT count(*) FROM notification_templates WHERE event LIKE 'kyc_%'` | `6` |
| Admin account exists | admin login at `/admin` | Dashboard loads |

Create these test accounts and record credentials in the shared sheet:

- `C-01` customer (phone + email)
- `S-01` seller (approved store)
- `B-01` Winga broker
- `A-01` platform admin

---

## 1. Customer sign-up & verification

| # | Step | Expected | Result |
|---|---|---|---|
| 1.1 | `POST /auth/register` or UI: sign up as C-01 | Account created, OTP sent via SMS+email | |
| 1.2 | Verify with wrong OTP | Rejected with error | |
| 1.3 | "Resend code" → `POST /auth/resend-verification` | `200`, new OTP delivered | |
| 1.4 | Verify correct OTP → `POST /auth/verify-account-otp` | Account `is_verified=true`, `status=active` | |
| 1.5 | Login C-01 | Access+refresh tokens; session persists | |
| 1.6 | Google sign-in (if enabled) | Account created/linked | |

## 2. Vendor (seller) onboarding

| # | Step | Expected | Result |
|---|---|---|---|
| 2.1 | Register seller S-01 | Pending status | |
| 2.2 | Upload all required KYC docs | Status → `under_review`; **email "under review" received** | |
| 2.3 | Admin: reject S-01 with a reason | Status `rejected`; **SMS+email with reason received** | |
| 2.4 | Fix docs, resubmit → admin approve | Status `approved`; **SMS+email "verified" received**; seller dashboard unlocked | |
| 2.5 | S-01 adds payout account (mobile money `0712…` format) | Saved as `2557…`, status `verified`, usable immediately | |
| 2.6 | S-01 re-adds same number as `+255…` | `409` friendly message, no duplicate row | |
| 2.7 | S-01 creates product (draft → submit) | Product pending review | |
| 2.8 | Admin approves product | Product visible on storefront | |

## 3. Product purchase (end-to-end)

| # | Step | Expected | Result |
|---|---|---|---|
| 3.1 | C-01 browses store, opens product, add to cart | Cart shows item + total | |
| 3.2 | C-01 adds delivery address | Address saved | |
| 3.3 | Checkout → `POST /orders` | Order created, `pending payment` | |
| 3.4 | `POST /payments/initiate` (Selcom MNO, test phone) | Push prompt sent to phone | |
| 3.5 | Confirm on phone / sandbox callback → `POST /payments/azampay/callback` | Payment `confirmed`, order `paid` | |
| 3.6 | Notifications | C-01 gets order confirmation (email+in-app); S-01 gets new-order alert | |
| 3.7 | S-01 accepts order → processing → ready-to-ship → dispatch | Status transitions work, C-01 notified each step | |
| 3.8 | Delivery proof / order delivered | Order `delivered`, escrow release milestone reached | |
| 3.9 | Edge: initiate payment, never confirm | Order stays unpaid; expiry worker cancels it (check `xerin-unpaid-order-expiry` — currently **failed** on server, fix first) | |

## 4. Commission calculation

| # | Step | Expected | Result |
|---|---|---|---|
| 4.1 | After 3.5 payment confirmed: `GET /commissions/orders/{order_id}` | Commission rows per item | |
| 4.2 | Verify math | `gross = commission + seller_net`; matches rule % | |
| 4.3 | `GET /commissions/seller/me/summary` as S-01 | Pending balance reflects commission | |
| 4.4 | After delivery/escrow milestone | Balance moves pending → available | |
| 4.5 | S-01 wallet page | Available/pending/held figures match API | |

## 5. Withdrawals (vendor)

| # | Step | Expected | Result |
|---|---|---|---|
| 5.1 | S-01 `POST /wallets/me/payouts` with available amount | Payout request `pending` | |
| 5.2 | Admin: `GET /wallets/admin/payouts` → approve | Payout `approved`; seller notified | |
| 5.3 | Wallet balance drops; transaction recorded | Ledger consistent | |
| 5.4 | Edge: request > available balance | Rejected `4xx` | |
| 5.5 | Edge: cancel a pending payout | `cancelled`, balance returned | |
| 5.6 | B-01 broker: add payout account → request payout → admin approve | Same flow works for broker wallet | |

## 6. Xerin Marketplace platform withdrawals

| # | Step | Expected | Result |
|---|---|---|---|
| 6.1 | Admin finance view: platform commission total | Matches sum of commission rows | |
| 6.2 | Platform payout/settlement flow | Funds move correctly per config | |
| 6.3 | Audit trail | `admin.*` actions recorded in audit log | |

## 7. Notifications spot-check

| # | Step | Expected | Result |
|---|---|---|---|
| 7.1 | Every key event | In-app notification created (`/notifications`) | |
| 7.2 | Email channel | Delivered (check spam folder too) | |
| 7.3 | SMS channel | Delivered via Africa's Talking | |

## 8. Sign-off

- [ ] All critical flows pass with zero errors
- [ ] No `Xerin Marketplace` text visible anywhere (brand audit)
- [ ] Mobile app build tested on-device
- [ ] Sample products populated for layman testers
- [ ] Issues log reviewed, blockers resolved

**Beta owner:** ___ **Date:** ___ **Environment:** ___
