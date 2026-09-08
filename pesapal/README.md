# CloudPay Tanzania — Pesapal Streamlit Simulation

This is a **standalone simulation project**. It does not integrate with or modify the Xerin marketplace backend/database.

The demo is designed to share the existing public subdomain through a URL path:

```text
https://api.xerinmarketplace.com/pesapal-demo/
```

The existing Xerin API continues serving its normal routes. Only `/pesapal-demo/` is reverse-proxied to this project.

## Simulation flow

1. User registers in the demo.
2. User logs in.
3. User chooses Starter, Business, or Pro.
4. Streamlit creates a Pesapal API 3.0 order.
5. Customer opens Pesapal hosted checkout.
6. Pesapal handles the payment/card details.
7. Pesapal redirects the browser to `/pesapal-demo/`.
8. Pesapal separately calls `/pesapal-demo/ipn`.
9. The demo verifies the `OrderTrackingId` with Pesapal `GetTransactionStatus`.
10. The SQLite demo order is updated to COMPLETED / FAILED / REVERSED / INVALID as returned by Pesapal.

The application never collects raw card number, CVV, or card expiry details.

## Project layout

```text
pesapal_streamlit_cloud/
├── app.py                         Streamlit registration/login/packages/payment UI
├── pesapal_client.py              Shared Pesapal authentication/status client
├── ipn_server.py                  Standalone FastAPI IPN receiver
├── register_ipn.py                Registers the public IPN URL with Pesapal
├── requirements.txt
├── .env.example
├── .streamlit/
│   └── config.toml                Runs Streamlit under /pesapal-demo
└── deploy/
    ├── nginx-pesapal-demo.conf    Nginx location blocks
    ├── cloudpay-streamlit.service systemd template for Streamlit
    ├── cloudpay-ipn.service       systemd template for the IPN service
    └── install_services.sh        Installs/enables both services
```

## 1. Upload and prepare the project on the VPS

Choose a directory that is separate from the Xerin backend, for example:

```bash
mkdir -p /var/pesapal-demo
cd /var/pesapal-demo
```

Extract/copy the project there, then:

```bash
cd pesapal_streamlit_cloud
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

## 2. Configure `.env`

Use your Pesapal **sandbox** credentials first:

```env
PESAPAL_ENV=sandbox
PESAPAL_CONSUMER_KEY=YOUR_KEY
PESAPAL_CONSUMER_SECRET=YOUR_SECRET

DEMO_BASE_PATH=pesapal-demo
PESAPAL_CALLBACK_URL=https://api.xerinmarketplace.com/pesapal-demo/
PESAPAL_IPN_URL=https://api.xerinmarketplace.com/pesapal-demo/ipn

PESAPAL_IPN_ID=
```

Do not commit or expose `.env`.

## 3. Test both services locally on the VPS

Terminal 1:

```bash
source .venv/bin/activate
streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.baseUrlPath pesapal-demo
```

Terminal 2:

```bash
source .venv/bin/activate
uvicorn ipn_server:app --host 127.0.0.1 --port 8502
```

Check them from the VPS:

```bash
curl -I http://127.0.0.1:8501/pesapal-demo/
curl http://127.0.0.1:8502/pesapal-demo/ipn/health
```

The second command should return a JSON response with `"status":"ok"`.

## 4. Install the services with systemd

Once `.env` and `.venv` are ready:

```bash
sudo ./deploy/install_services.sh
```

The script installs:

```text
cloudpay-streamlit.service  -> 127.0.0.1:8501
cloudpay-ipn.service        -> 127.0.0.1:8502
```

Useful commands:

```bash
sudo systemctl status cloudpay-streamlit cloudpay-ipn
sudo journalctl -u cloudpay-streamlit -f
sudo journalctl -u cloudpay-ipn -f
```

## 5. Add Nginx routing to the EXISTING `api.xerinmarketplace.com` server block

Open:

```text
deploy/nginx-pesapal-demo.conf
```

Copy its three `location` blocks into the existing HTTPS `server { ... }` block for `api.xerinmarketplace.com`.

**Do not replace the current Xerin proxy configuration.** These are additional, more-specific routes only.

Then validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Public checks:

```bash
curl -I https://api.xerinmarketplace.com/pesapal-demo/
curl https://api.xerinmarketplace.com/pesapal-demo/ipn/health
```

At this stage the browser should also open:

```text
https://api.xerinmarketplace.com/pesapal-demo/
```

## 6. Register the Pesapal IPN URL

Only do this after the public IPN health route is working over HTTPS.

```bash
source .venv/bin/activate
python register_ipn.py
```

Pesapal returns an `ipn_id`. Add it to `.env`:

```env
PESAPAL_IPN_ID=THE_RETURNED_ID
```

Restart both demo services:

```bash
sudo systemctl restart cloudpay-streamlit cloudpay-ipn
```

## 7. Run the payment simulation

Open:

```text
https://api.xerinmarketplace.com/pesapal-demo/
```

Then:

```text
Register -> Login -> Choose package -> Pay securely with Pesapal
```

After checkout, the browser callback and the server IPN both use the same standalone simulation project. The Xerin marketplace backend is not involved.

## Existing Xerin API safety

The Nginx configuration intentionally routes only these paths away from the current backend:

```text
/pesapal-demo/*
```

Routes such as these remain on the existing Xerin backend:

```text
/
/docs
/orders/...
/payments/...
```

## Sandbox / live

Sandbox:

```env
PESAPAL_ENV=sandbox
```

Live:

```env
PESAPAL_ENV=live
```

Do not switch this simulation to live payments until your Pesapal merchant account is approved and you intentionally want to process real money.
