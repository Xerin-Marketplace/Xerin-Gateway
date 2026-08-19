Xerin Phase 2 Task 8 - Swagger/OpenAPI HOTFIX

Error:
PydanticUserError:
TypeAdapter[Annotated[ForwardRef('ShipmentStatus | None'), ...]] is not fully defined

Root cause:
Task 8 added this FastAPI query parameter in api/routers/orders.py:

    shipment_status: ShipmentStatus | None = Query(default=None, alias="status")

but ShipmentStatus was not imported into orders.py.

Because the module uses postponed annotations, the app can start successfully,
but FastAPI/OpenAPI later fails while resolving the ForwardRef for /openapi.json.

Fix:
Added ShipmentStatus to the existing api.enums import in api/routers/orders.py.

No database migration is required.
No model or schema changes are required.
