from api.main import api
from api.models import SellerWallet,WalletTransaction,PayoutRequest,PayoutEvent
from api.enums import PermissionCode,PayoutStatus,WalletTransactionType
def test_wallet_models_exist(): assert SellerWallet.__tablename__=="seller_wallets" and WalletTransaction.__tablename__=="wallet_transactions"
def test_payout_models_exist(): assert PayoutRequest.__tablename__=="payout_requests" and PayoutEvent.__tablename__=="payout_events"
def test_wallet_permissions_exist(): assert PermissionCode.wallet_read.value=="wallet:read" and PermissionCode.wallet_manage.value=="wallet:manage"
def test_wallet_routes_registered():
    paths = set(api.openapi()["paths"].keys())

    assert "/api/v1/wallet/me" in paths
    assert "/api/v1/wallet/me/payouts" in paths
    assert "/api/v1/wallet/admin/payouts/{payout_id}" in paths
