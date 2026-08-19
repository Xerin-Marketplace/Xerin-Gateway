# Phase 3 Task 3 — Logistics Company Delivery Zones

Copy the included files into the backend root while preserving their paths.

Run:

```bash
source .venv/bin/activate
python -c "from api.main import api; print('API import successful')"
alembic upgrade head
python -m pytest tests/test_phase3_logistics_task3_zones.py -v
python -m pytest -m "not integration" -v
python -m compileall api
```

Expected Alembic head:

```text
p26_logistics_delivery_zones
```
