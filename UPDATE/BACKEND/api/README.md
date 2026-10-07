# Phase 1 — Task 3

Files:
- `models.py` → `api/models.py`
- `security.py` → `api/security.py`
- `auth.py` → `api/routers/auth.py`
- `alembic/versions/phase1_task3_security_constraints.py` → your Alembic versions directory
- `PREFLIGHT.sql` → run against PostgreSQL before migration

The migration intentionally deletes existing refresh sessions and invalidates outstanding OTPs. Users must sign in again and request new OTPs.

Before running, confirm your current Alembic head:

```bash
alembic current
alembic heads
```

The migration assumes the previous revision is `add_otp_purpose`. If your actual current head has a different revision ID, edit:

```python
down_revision = "add_otp_purpose"
```

Then run:

```bash
python -m compileall api
alembic upgrade head
```
