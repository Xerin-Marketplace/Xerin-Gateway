Xerin Phase 2 Task 1 HOTFIX

Problem:
api/schemas.py raised:
NameError: name 'SellerResponse' is not defined

Cause:
The Task 1 Address schema replacement accidentally removed an existing block of
seller/store schemas located between AddressCreate and PaginatedAddressResponse.

Restored schemas include:
- SellerCreate / SellerUpdate / SellerResponse
- SellerRegisterRequest
- SellerApplicationRequest / SellerApplicationStatusResponse
- SellerKYCCreate / SellerKYCResponse / SellerKYCStatusResponse
- SellerPayoutCreate / SellerPayoutResponse
- SellerProfileUpdate / SellerProfileResponse
- StoreUpdate / StoreResponse / StorePublicResponse
- PaginatedAdminStoreResponse / PaginatedStoreResponse
- UserMeResponse

The Phase 2 Task 1 address enhancements remain intact:
- formatted_address
- place_id
- delivery_instructions
- is_active
- is_verified
- delivery_ready
- pagination/search/filter changes

No database migration change is required.
Keep p19_customer_delivery_locations as the current migration head.
