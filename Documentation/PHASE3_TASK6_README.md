# Phase 3 Combined Task 6 — Integrations and Dashboard

```bash
source .venv/bin/activate
python -c "from api.main import api; print('API import successful')"
alembic upgrade head
python -m pytest tests/test_phase3_logistics_task6_integration_dashboard.py -v
python -m pytest -m "not integration" -v
```

Expected Alembic head: `p29_logistics_integration_dashboard`.
