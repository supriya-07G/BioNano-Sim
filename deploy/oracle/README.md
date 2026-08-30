# Vercel frontend + Oracle backend, over a Cloudflare tunnel

The permanent deployment: React on a CDN, the API on a VM with real memory,
and HTTPS between them without buying a domain or opening a port.

```
browser ──https──> yourapp.vercel.app        (static build, global CDN)
   │
   └────https──> <random>.trycloudflare.com  (Cloudflare edge)
                        │
                        └── outbound tunnel ── Oracle VM ── backend:8000
```

The tunnel **dials out** to Cloudflare. Nothing listens on the VM's public
interface, so neither the OCI security list nor the VM's own `iptables` needs
changing — which is where most Oracle deployments stall.

---

## 1. The VM

Oracle Cloud → Compute → Instances → Create.

- **Shape:** `VM.Standard.A1.Flex` (Ampere, Always Free) — 4 OCPU / 24 GB is
  the full free allowance. `VM.Standard.E2.1.Micro` (x86) also works and is
  more often available, but 1 GB of RAM is tight for OpenMM.
- **Image:** Ubuntu 22.04 or 24.04
- Save the SSH private key when it is offered. There is no second chance.

> **"Out of host capacity"** on Ampere is common and can persist for days. It
> is a real capacity limit, not a mistake on your part. Either retry across
> different availability domains, or take the x86 micro shape. Do not plan a
> deadline around getting an A1.

## 2. Docker on the VM

```bash
ssh -i your-key.pem ubuntu@<vm-public-ip>
```

```bash
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER
```

Log out and back in so the group membership applies.

## 3. Bring it up

```bash
git clone https://github.com/supriya-07G/BioNano-Sim.git && cd BioNano-Sim
```

```bash
docker compose -f deploy/oracle/docker-compose.yml up -d --build
```

The first build takes 5–10 minutes, most of it installing OpenMM. Then read
the tunnel's URL out of its log:

```bash
docker compose -f deploy/oracle/docker-compose.yml logs tunnel | grep trycloudflare
```

You get `https://<random-words>.trycloudflare.com`. Check it:

```bash
curl https://<random-words>.trycloudflare.com/api/v1/system/readiness
```

All seven components should report ready.

## 4. Point Vercel at it

Import the repo at [vercel.com/new](https://vercel.com/new). `vercel.json` at
the repo root already sets the build command, output directory and the SPA
rewrite, so leave the framework preset alone.

Add one environment variable:

| Name | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<random-words>.trycloudflare.com` |

**The origin only — no `/api/v1`.** `services/api.ts` appends `/api/v1`
itself, so including it produces `/api/v1/api/v1/...` and every request 404s.

Redeploy after setting it: Vite bakes environment variables in at build time,
so a variable added after a build has no effect until the next one.

## 5. Let the backend accept the Vercel origin

Back on the VM, with your real Vercel URL:

```bash
VERCEL_ORIGINS=https://your-app.vercel.app docker compose -f deploy/oracle/docker-compose.yml up -d
```

Without this the browser blocks every call as a CORS failure. The default in
the compose file is a placeholder, not your URL.

---

## Without Docker

Docker is not required. Nothing about the tunnel needs it -- `cloudflared` is a
single binary and runs fine under systemd.

The one real constraint is the interpreter: `scripts/validate_model.py` asserts
Python **3.11** exactly, because the model bundle was fitted under 3.11 with
scikit-learn 1.7.1. Ubuntu 22.04 ships 3.10 and 24.04 ships 3.12, so neither
default works. `uv` installs 3.11 without touching the system Python.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && exec $SHELL
git clone https://github.com/supriya-07G/BioNano-Sim.git && cd BioNano-Sim
uv venv .venv311 --python 3.11
uv pip install --python .venv311 -r backend/requirements.txt
.venv311/bin/python scripts/setup_local.py
.venv311/bin/python scripts/validate_model.py    # must print 25/25
```

Install `cloudflared`:

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$(dpkg --print-architecture) -o cloudflared
sudo install -m755 cloudflared /usr/local/bin/cloudflared
```

Two systemd units. `/etc/systemd/system/bionano-api.service`:

```ini
[Unit]
Description=BioNano-Sim API
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/BioNano-Sim
# --app-dir backend is required: every internal import is `from app.…` and
# there is no backend/__init__.py, so `backend.app.main:app` fails with
# ModuleNotFoundError.
ExecStart=/home/ubuntu/BioNano-Sim/.venv311/bin/uvicorn app.main:app     --host 127.0.0.1 --port 8000 --app-dir backend
Environment=BIONANO_CORS_ORIGINS=https://your-app.vercel.app
Environment=OPENMM_CPU_THREADS=2
Environment=BIONANO_MAX_CONCURRENT_JOBS=1
Environment=BIONANO_MAX_PRODUCTION_STEPS=20000
Environment=BIONANO_JOB_WALL_CLOCK_LIMIT_S=600
Restart=always

[Install]
WantedBy=multi-user.target
```

Binding to `127.0.0.1` rather than `0.0.0.0` is deliberate: only the tunnel
needs to reach it, so the API is never on the VM's public interface.

`/etc/systemd/system/bionano-tunnel.service`:

```ini
[Unit]
Description=Cloudflare tunnel for BioNano-Sim
After=bionano-api.service
Requires=bionano-api.service

[Service]
User=ubuntu
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bionano-api bionano-tunnel
sudo journalctl -u bionano-tunnel | grep trycloudflare   # your HTTPS URL
```

### Which to pick

| | Docker compose | systemd + uv |
|---|---|---|
| Python 3.11 | pinned by the image | pinned by `uv` |
| Steps to run | one command | two unit files |
| Memory overhead | ~100 MB for the daemon | none |
| Matches what CI tested | yes, same image | close, not identical |
| Debugging a failure | `docker logs` | `journalctl` |

On a 1 GB `E2.1.Micro` the systemd route is the better trade -- the Docker
daemon's overhead is a real fraction of that box. On a 24 GB Ampere it makes
no practical difference, and compose is fewer moving parts to get wrong.

## A fixed hostname instead of a random one

The quick tunnel's URL changes whenever the `tunnel` container restarts, and
each change means re-setting `VITE_API_BASE_URL` and redeploying Vercel. If
you own a domain and put it on Cloudflare (free), a **named tunnel** gives a
permanent hostname:

1. Cloudflare Zero Trust → Networks → Tunnels → Create a tunnel
2. Copy the token
3. Replace the `tunnel` service's command with:

```yaml
    command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
```

4. Route the hostname to `http://backend:8000` in the Cloudflare dashboard.

## Operating it

```bash
docker compose -f deploy/oracle/docker-compose.yml logs -f backend
```

```bash
docker compose -f deploy/oracle/docker-compose.yml exec backend python scripts/cleanup_runtime.py
```

Job results live on the `bionano-runtime` volume and survive restarts. `data/`
and `models/` are baked into the image and deliberately not mounted: they are
the evidence a scientific claim rests on, and a volume would let them drift
from the commit that produced them.

## Deliberate limits

| Variable | Value | Why |
|---|---|---|
| `BIONANO_MAX_CONCURRENT_JOBS` | 1 | one OCPU is not four |
| `BIONANO_MAX_PRODUCTION_STEPS` | 20,000 | bounds a single request's cost |
| `BIONANO_JOB_WALL_CLOCK_LIMIT_S` | 600 | fail visibly rather than hang |
| `OPENMM_CPU_THREADS` | 2 | leaves headroom for the API to stay responsive |
| memory limit | 6 GB | one runaway job must not take the tunnel down with it |

## What was verified before writing this

The decoupled setup was exercised locally, not assumed: the production bundle
was built with `VITE_API_BASE_URL` pointing at a different origin, served from
`:4173`, and driven against the API on `:8000`.

| Check | Result |
|---|---|
| Runtime dependencies cover every backend import | fastapi, openmm, mdtraj, numpy, pandas, joblib, pydantic — all pinned in `requirements.txt` |
| `VITE_API_BASE_URL` is baked into the bundle at build time | confirmed present in `dist/assets/index-*.js` |
| No request bypasses `API_PREFIX` | no hardcoded `/api` fetches in the built output |
| CORS preflight from another origin | `200`, correct `allow-methods` and `allow-origin` |
| Dashboard cross-origin | 5 proteins, all components ready |
| Results page cross-origin | 5 charts, both 3D viewers rendering, structure fetches `200` |
| Report download | `200`, `Content-Disposition` readable by JavaScript |
| Multipart upload | `200`, returned an `upload_id` |

`uvicorn app.main:app --app-dir backend` was also checked against the
alternative `backend.app.main:app`, which fails with `ModuleNotFoundError: No
module named 'app'` — there is no `backend/__init__.py` and every internal
import is `from app.…`.

## Known caveats

- **The tunnel URL is public and unauthenticated.** Unguessable, but anyone
  holding it can start simulations on your VM. The step and wall-clock caps
  above bound the damage; they do not prevent it.
- **Quick-tunnel URLs are not stable across restarts.** See the named-tunnel
  section.
- **Free-tier Oracle VMs can be reclaimed** if idle for long periods. Check it
  is still up before you rely on it.
