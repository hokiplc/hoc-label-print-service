# hoc-label-print-service

LAN-only label-printing microservice for a Brother QL-700, running on a Raspberry Pi.
Accepts print jobs (e.g. from a WooCommerce plugin) over HTTP, renders a branded
62mm coffee bag label, and prints it.

Not for public internet exposure — designed to run as a dedicated small appliance
on a local business network.

## Architecture

- **FastAPI** app (`app/main.py`) serving JSON API + a minimal admin UI.
- **SQLite** job store (`app/db.py`) — survives restarts, keeps job history.
- **In-process worker queue** (`app/queue_worker.py`) — one or more background
  threads pull jobs off a `queue.Queue` and print sequentially, so concurrent
  requests never collide on the single USB printer.
- **Pillow-based template renderer** (`app/templates/`) — turns structured JSON
  into a label image. Templates are a fixed, server-side registry; clients can
  never submit arbitrary markup, code, or file paths.
- **brother_ql** — converts the rendered image to QL raster instructions and
  sends them over USB.

## API

All endpoints except `GET /health` require an `X-API-Key` header matching
`HOC_API_KEY`, and the client IP must fall within `HOC_ALLOWED_CIDRS`.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service health, printer config, queue depth, version. No auth. |
| GET | `/config` | Non-secret runtime configuration. |
| POST | `/print-jobs` | Submit a print job (queued, returns immediately with `202`). |
| POST | `/print-jobs/preview` | Render a job and return a PNG, without printing. |
| GET | `/print-jobs/{job_id}` | Get a job's status. |
| GET | `/jobs` | List recent jobs. |
| POST | `/jobs/{job_id}/reprint` | Requeue a completed/failed job. |
| POST | `/admin/test-print` | Print a built-in test label. |
| GET | `/` | Minimal mobile-friendly admin UI. |

### Print job payload

```json
{
  "template": "house-of-coffee-62mm",
  "printer": "ql-700",
  "label_width_mm": 62,
  "copies": 1,
  "job_ref": "order-18452-item-3",
  "data": {
    "product_name": "DARK MONSOON MALABAR",
    "grind": "AeroPress",
    "weight": "0.454 kg",
    "strength": "4",
    "flavour": "3",
    "roast": "3",
    "best_before": "04.08.2027"
  }
}
```

- `template` must be one of the server's enabled templates (currently
  `house-of-coffee-62mm`). Unknown or disabled templates are rejected with `400`.
- `data.product_name` is required; all other `data` fields are optional and
  blank if omitted.
- `copies` must be `>= 1`.
- If `job_ref` is resubmitted within `HOC_IDEMPOTENCY_WINDOW_SECONDS` and the
  prior job for that ref hasn't failed/cancelled, the existing job is returned
  instead of creating a duplicate print.

### curl examples

```bash
API=http://raspberrypi.local:8080
KEY=change-me-to-a-long-random-string

# Health (no auth)
curl -s $API/health | jq

# Config
curl -s -H "X-API-Key: $KEY" $API/config | jq

# Submit a print job
curl -s -X POST $API/print-jobs \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "template": "house-of-coffee-62mm",
    "job_ref": "order-18452-item-3",
    "data": {
      "product_name": "DARK MONSOON MALABAR",
      "grind": "AeroPress",
      "weight": "0.454 kg",
      "strength": "4",
      "flavour": "3",
      "roast": "3",
      "best_before": "04.08.2027"
    }
  }' | jq

# Preview without printing (saves a PNG response)
curl -s -X POST $API/print-jobs/preview \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"template": "house-of-coffee-62mm", "data": {"product_name": "Preview Coffee"}}' \
  -o preview.png

# Job status
curl -s -H "X-API-Key: $KEY" $API/print-jobs/<job_id> | jq

# Recent jobs
curl -s -H "X-API-Key: $KEY" "$API/jobs?limit=20" | jq

# Reprint
curl -s -X POST -H "X-API-Key: $KEY" $API/jobs/<job_id>/reprint | jq

# Built-in test print
curl -s -X POST -H "X-API-Key: $KEY" $API/admin/test-print | jq
```

## Configuration

Configuration comes from `config.yaml` (optional, see `config.yaml.example`)
and/or environment variables (see `.env.example`), which always win over the
file. Key settings: `HOC_API_KEY`, `HOC_ALLOWED_CIDRS`, `HOC_DEFAULT_PRINTER_MODEL`,
`HOC_DEFAULT_LABEL_WIDTH_MM`, `HOC_PRINTER_IDENTIFIER`, `HOC_QUEUE_CONCURRENCY`,
`HOC_PREVIEW_DIR`, `HOC_LOG_DIR`, `HOC_DB_PATH`, `HOC_FONT_DIR`.

## Raspberry Pi deployment

### 1. Prerequisites

- Raspberry Pi OS (Bookworm or later recommended).
- Brother QL-700 connected via USB, with 62mm continuous label roll loaded.
- A stable LAN address for the Pi (see below) so the WooCommerce plugin's
  configured endpoint never changes.

#### Give the Pi a stable LAN address

Pick **one** of the following. A router-side DHCP reservation is usually
simplest and easiest to change later without touching the Pi.

**Option A — DHCP reservation on the router (recommended)**

1. Find the Pi's MAC address: `ip link show wlan0` or `ip link show eth0`
   (look for the `link/ether` value).
2. In your router's admin UI, find "DHCP reservations" / "Address reservation"
   / "Static leases" (naming varies by vendor) and bind that MAC address to a
   free IP outside the router's dynamic pool, e.g. `192.168.1.50`.
3. Reboot the Pi (or release/renew its lease) and confirm with `hostname -I`.

**Option B — Static IP on the Pi itself, via `dhcpcd` (Bookworm and earlier
default network manager)**

```bash
sudo nano /etc/dhcpcd.conf
```

Append (adjust subnet, gateway, and DNS to match your network):

```
interface eth0
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 1.1.1.1
```

```bash
sudo systemctl restart dhcpcd
```

**Option C — Static IP via NetworkManager (Raspberry Pi OS Bookworm default
on some images, or if you've switched to NetworkManager)**

```bash
nmcli connection show              # find your connection name, e.g. "Wired connection 1"
sudo nmcli connection modify "Wired connection 1" \
  ipv4.addresses 192.168.1.50/24 \
  ipv4.gateway 192.168.1.1 \
  ipv4.dns "192.168.1.1 1.1.1.1" \
  ipv4.method manual
sudo nmcli connection up "Wired connection 1"
```

Verify with `ip a` and `ping <router-ip>` after either option, then point the
WooCommerce plugin at `http://<that-ip>:8080`.

### 2. Install

```bash
git clone <this-repo> hoc-label-print-service
cd hoc-label-print-service
sudo ./deploy/install.sh
```

This installs OS packages, creates a dedicated `hoclabel` system user, sets up
a virtualenv under `/opt/hoc-label-print`, installs a udev rule for USB printer
access, and registers (but does not start) the systemd service.

### 3. Configure

```bash
sudo nano /opt/hoc-label-print/.env
```

Set `HOC_API_KEY` to a long random string, and `HOC_ALLOWED_CIDRS` to your LAN
range (e.g. `192.168.1.0/24`).

Install fonts (see `fonts/README.md`):

```bash
sudo apt-get install -y fonts-dejavu-core
sudo cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /opt/hoc-label-print/fonts/
sudo cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf /opt/hoc-label-print/fonts/
```

### 4. USB access

The installer adds a udev rule (`deploy/99-brother-ql700.rules`) granting the
`hoclabel` user's group access to the QL-700's USB vendor/product ID, and adds
`hoclabel` to `plugdev`. Re-plug the printer (or reboot) after install so the
rule takes effect.

### 5. Boot persistence

```bash
sudo systemctl enable hoc-label-print   # already done by install.sh
sudo systemctl start hoc-label-print
sudo systemctl status hoc-label-print
```

The service restarts automatically on failure (`Restart=on-failure` in the
systemd unit) and starts automatically on every boot.

### 6. Diagnostics

```bash
sudo -u hoclabel /opt/hoc-label-print/.venv/bin/python -m scripts.diagnostics
```

Checks: printer detected over USB, label width config, font files present,
and that data/log/preview directories are writable. Exits non-zero if any
check fails — suitable for a cron-based health check or monitoring script.

`GET /health` is suitable for uptime monitoring tools (Uptime Kuma, healthchecks.io
push, etc.) — it returns `200` with `status: "ok"` plus queue depth and worker
liveness, with no auth required.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit HOC_API_KEY etc.
uvicorn app.main:app --reload --port 8080
```

Without a physical printer attached, `/print-jobs` will queue and then fail at
the print stage with a structured `PrinterNotFoundError` message recorded on
the job — useful for testing the API end-to-end. `/print-jobs/preview` works
fully offline since it never touches the printer.

## Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

Tests cover payload validation, auth/CIDR enforcement, idempotency-window
replay, job creation/lookup, and template rendering — they do not require a
physical printer.

## Security notes

- LAN-local by design: no CORS, bind to your LAN interface, restrict by CIDR,
  require a shared API key.
- Templates are a fixed server-side registry; the API never accepts HTML,
  code, or file paths from callers.
- Rate limiting (`HOC_RATE_LIMIT_PER_MINUTE`, default 60/min per client IP)
  via slowapi.
- Logs never include the API key or other secrets.
