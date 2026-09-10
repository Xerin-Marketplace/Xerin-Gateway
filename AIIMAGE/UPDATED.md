# Task 1 — Backend AI Product Image Improvement Engine

Updated/added:
- `api/config.py`
- `api/services/product_ai_image_service.py`
- `api/routers/products.py`

No database migration is required.

## What Task 1 does

Adds a secure backend-only OpenRouter image-editing pipeline.

New seller endpoint:

    POST /api/v1/products/{product_id}/images/ai-improve

Multipart fields:
- `file`: the seller's original JPEG/PNG/WEBP
- `is_primary`: true/false

The endpoint:
1. verifies the authenticated seller owns the product;
2. never exposes the OpenRouter key to the browser;
3. sends the seller's real photo as `input_references`;
4. uses a restrictive product-preservation prompt;
5. receives the improved image;
6. re-runs Xerin's existing deterministic image-quality gate;
7. returns a temporary PNG preview with `Cache-Control: no-store`;
8. does **not** save/attach the AI image to the product yet.

Task 2 will add the seller popup/preview/accept flow.

## Environment

Add to backend `.env`:

    PRODUCT_IMAGE_AI_ENABLED=true
    OPENROUTER_API_KEY=YOUR_REAL_KEY_HERE
    PRODUCT_IMAGE_AI_MODEL=openai/gpt-image-1
    PRODUCT_IMAGE_AI_TIMEOUT_SECONDS=120
    PRODUCT_IMAGE_AI_RESOLUTION=1K
    PRODUCT_IMAGE_AI_QUALITY=high

Do not place `OPENROUTER_API_KEY` in Next.js `.env` or any `NEXT_PUBLIC_*` variable.

The model is configurable. Before switching models, confirm that the OpenRouter image endpoint reports support for `input_references` and the parameters used by this request.

## Important behavior

AI is never trusted automatically. The generated output is checked again by:
- dimensions
- megapixels
- aspect ratio
- sharpness
- brightness
- primary-image white-background rule

The response headers include:
- `X-Xerin-AI-Model`
- `X-Xerin-Image-Width`
- `X-Xerin-Image-Height`
- `X-Xerin-Quality-Passed`
- `X-Xerin-Quality-Score`
- `X-Xerin-Quality` (URL-safe base64 JSON details)

## Deploy

    cd /var/Xerin-Gateway/BACKEND
    source .venv/bin/activate

    python -m py_compile \
      api/config.py \
      api/services/product_ai_image_service.py \
      api/routers/products.py

    sudo systemctl restart xerin-api
    sudo systemctl status xerin-api --no-pager

## Notes

- Uses `requests`, already present in the backend dependency set.
- No frontend files are changed in Task 1.
- No AI image is permanently stored until the seller explicitly accepts it in the next task.
