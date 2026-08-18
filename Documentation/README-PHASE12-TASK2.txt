Xerin Phase 12 Task 2 - Admin Advertisement API

New permissions:
- advertisements:read
- advertisements:manage

Admin endpoints:
GET    /api/v1/admin/advertisements
POST   /api/v1/admin/advertisements
GET    /api/v1/admin/advertisements/{advertisement_id}
PATCH  /api/v1/admin/advertisements/{advertisement_id}
DELETE /api/v1/admin/advertisements/{advertisement_id}
POST   /api/v1/admin/advertisements/{advertisement_id}/activate
POST   /api/v1/admin/advertisements/{advertisement_id}/pause

Features:
- create/edit/list/delete advertisements
- activate immediately or schedule for a future starts_at
- pause without changing campaign dates
- exact timezone-aware start/end date-time validation
- expired advertisements cannot be reactivated until ends_at is extended
- effective status filtering: draft, scheduled, active, paused, expired
- placement filtering and search
- pagination
- priority
- billing metadata
- admin activity audit logs for create/update/activate/pause/delete
- default admin role receives read/manage permissions
- super_admin automatically receives both because it receives every PermissionCode

Important:
After deploying the code, run:
    python -m api.seed_permissions
This inserts the two new permission rows and grants them to the default admin role.

Database migration:
No new Alembic migration for Task 2. Task 1's p14_advertising_foundation
already created the advertisement table and enums.

Frontend:
No frontend changes in Task 2. Admin UI comes in Phase 12 Task 4.
