# Phase 3 Combined Task 4 — Distance and Multi-Seller Pricing

Copy the included files into the backend root while preserving their paths.

```bash
source .venv/bin/activate
python -c "from api.main import api; print('API import successful')"
alembic upgrade head
python -m pytest tests/test_phase3_logistics_task4_pricing.py -v
python -m pytest -m "not integration" -v
python -m compileall api
```

Expected Alembic head: `p27_logistics_pricing`.
