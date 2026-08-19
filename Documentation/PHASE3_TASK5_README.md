# Phase 3 Combined Task 5 — Pickup Jobs and Tracking

```bash
source .venv/bin/activate
python -c "from api.main import api; print('API import successful')"
alembic upgrade head
python -m pytest tests/test_phase3_logistics_task5_pickup_tracking.py -v
python -m pytest -m "not integration" -v
python -m compileall api
```

Expected Alembic head: `p28_logistics_pickup_tracking`.
