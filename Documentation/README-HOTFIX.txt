Xerin Phase 2 Task 7 - Swagger/OpenAPI HOTFIX

Error:
PydanticUserError: TypeAdapter[...Body_upload_logistics_pickup_proof...] is not fully defined

Root cause:
api/routers/logistics.py uses Decimal in the multipart FastAPI endpoint:

    latitude: Decimal = Form(...)
    longitude: Decimal = Form(...)

but Decimal was not imported.

Because the module uses:
    from __future__ import annotations

the missing symbol did not necessarily stop module import. FastAPI encountered it
later while generating /openapi.json for Swagger docs.

Fix:
Added:
    from decimal import Decimal

No database migration is required.
No schema/model changes are required.
