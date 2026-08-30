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

## 2. Run the backend

Two ways. Both work; pick one and stay with it, because the auto-deploy
workflow needs to know which.

### Option A — Docker Compose

Fewer steps, and the image pins Python 3.11 for you.

```bash
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER
```

Log out and back in, then:

```bash
git clone https://github.com/supriya-07G/BioNano-Sim.git && cd BioNano-Sim
docker compose -f deploy/oracle/docker-compose.yml up -d --build
```

The first build takes 5–10 minutes, most of it installing OpenMM. The compose
file runs both the API and `cloudflared`, so the tunnel URL is in its log:

```bash
docker compose -f deploy/oracle/docker-compose.yml logs tunnel | grep trycloudflare
```

The API is not published to the host — only the tunnel reaches it, over the
compose network.

Set `VM_DEPLOY_MODE=docker` as a repository variable if you use auto-deploy.

### Option B — uv + systemd

No daemon, and `journalctl` rather than a container boundary between you and a
failure. Better on a 1 GB `E2.1.Micro`, where Docker's memory is a real
fraction of the box.

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

### Which one

| | Docker Compose | uv + systemd |
|---|---|---|
| Python 3.11 | pinned by the image | pinned by `uv` |
| Steps | one command | two unit files |
| Memory overhead | ~100 MB daemon | none |
| Reading a failure | `docker compose logs` | `journalctl` |
| Tunnel | runs as a compose service | runs as a systemd unit |

On a 24 GB Ampere it makes little practical difference and Compose is fewer
things to get wrong. On a 1 GB `E2.1.Micro`, systemd is the better trade.

Whichever you pick, set `VM_DEPLOY_MODE` to match (`docker` or `systemd`) if
you enable auto-deploy — the workflow restarts the service differently for
each.

## Without Cloudflare: Caddy + nip.io

Cloudflare is not required, but **something** must provide HTTPS. Vercel serves
the frontend over HTTPS and a browser hard-blocks an HTTPS page calling an HTTP
API -- mixed content, with no override. So `http://<ip>:8000` cannot work from
Vercel however the firewall is configured.

`nip.io` resolves `<ip>.nip.io` to that IP, and Let's Encrypt issues for it, so
Caddy gets a real certificate with no domain purchased.

**1. Open 80 and 443 -- in both firewalls.** This is the step that catches
people: Oracle images ship their own `iptables` rules on top of the OCI
security list, and opening only one leaves the port silently unreachable.

OCI console → your VM → Subnet → Security List → Add Ingress Rules:
`0.0.0.0/0` to TCP 80 and 443.

Then on the VM:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

**2. Install Caddy:**

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

**3. Install the Caddyfile**, replacing the host with your VM's public IP:

```bash
sudo cp deploy/oracle/Caddyfile /etc/caddy/Caddyfile
sudo sed -i "s/129-146-1-23/$(curl -s ifconfig.me | tr '.' '-')/" /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

**4. Check it:**

```bash
curl https://$(curl -s ifconfig.me | tr '.' '-').nip.io/api/v1/health
```

Certificate issuance takes a few seconds on first request. Then set
`VITE_API_BASE_URL` in Vercel to `https://<ip-with-dashes>.nip.io`.

### Which front door

| | Cloudflare tunnel | Caddy + nip.io |
|---|---|---|
| Firewall changes | **none** | 80 + 443 in *two* firewalls |
| Public listeners on the VM | none | Caddy on 80/443 |
| URL stability | **changes** on tunnel restart | **stable**, derived from the IP |
| Set `VITE_API_BASE_URL` | on every tunnel restart | once |
| Extra moving part | `cloudflared` | `caddy` |

For a Vercel pairing the stable hostname usually wins: a quick tunnel's URL
changing means editing the Vercel variable and redeploying the frontend each
time. If you would rather open no ports at all, keep the tunnel and accept
that cost -- or use a named tunnel, which is stable but needs a domain on
Cloudflare.

> `nip.io` has occasionally hit Let's Encrypt rate limits during outages.
> `sslip.io` works identically as a fallback: `<ip>.sslip.io`.

## Auto-deploy from GitHub

With the systemd setup above, `.github/workflows/deploy-backend.yml` makes
GitHub the source of truth for both halves: Vercel rebuilds the frontend on
every push, this pulls and restarts the API.

Add under **Settings -> Secrets and variables -> Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `VM_SSH_KEY` | the VM's private key, whole file including the BEGIN/END lines |
| Variable | `VM_HOST` | the VM's public IP |
| Variable | `VM_USER` | `ubuntu` |
| Variable | `VM_APP_DIR` | `/home/ubuntu/BioNano-Sim` |
| Variable | `VM_DEPLOY_MODE` | `docker` or `systemd` (defaults to `systemd`) |

The VM user needs to restart the service without a password prompt:

```bash
echo "ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart bionano-api, /bin/systemctl is-active bionano-api, /usr/bin/journalctl -u bionano-api *" | sudo tee /etc/sudoers.d/bionano
```

What the workflow does, and why:

- **Skips with a notice** when the four settings are absent, rather than
  failing -- an unconfigured repo should not show a permanent red X.
- **Reinstalls dependencies only when `requirements.txt` changed.**
  Reinstalling the scientific stack takes minutes; a code-only change should
  redeploy in seconds.
- **Runs `validate_model.py` before restarting**, so the service is never
  restarted onto a bundle that no longer reproduces its published metrics.
- **Verifies the service came back** and dumps the last 40 journal lines if it
  did not. A deploy that silently leaves the API down is worse than one that
  fails loudly.
- **Pins the host key** with `ssh-keyscan` instead of disabling host
  verification.

Note this deploys the **backend only**. The tunnel is unaffected -- it keeps
running and its URL does not change, because only `bionano-api` restarts.

## A fixed hostname instead of a random one

The quick tunnel's URL changes whenever the `tunnel` container restarts, and
each change means re-setting `VITE_API_BASE_URL` and redeploying Vercel. If
you own a domain and put it on Cloudflare (free), a **named tunnel** gives a
permanent hostname:

1. Cloudflare Zero Trust → Networks → Tunnels → Create a tunnel
2. Copy the token
3. Replace the `tunnel` service's command with:

```ini
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token <TOKEN>
```

in `bionano-tunnel.service`, then `sudo systemctl daemon-reload && sudo systemctl restart bionano-tunnel`.

4. Route the hostname to `http://127.0.0.1:8000` in the Cloudflare dashboard.

## Operating it

**Docker Compose:**

```bash
docker compose -f deploy/oracle/docker-compose.yml logs -f backend
docker compose -f deploy/oracle/docker-compose.yml restart backend
docker compose -f deploy/oracle/docker-compose.yml exec backend python scripts/cleanup_runtime.py
```

**systemd:**

```bash
sudo journalctl -u bionano-api -f
sudo systemctl restart bionano-api
cd ~/BioNano-Sim && .venv311/bin/python scripts/cleanup_runtime.py
```

Add `--apply` to the cleanup command to actually delete; it previews by
default.

Job results live under `runtime/`, which is a plain directory on the VM and
survives restarts. `data/` and `models/` are tracked in git and change only
with a deploy, which is the point: they are the evidence a scientific claim
rests on, and they should move only when the commit that produced them does.

Diagnostics, redacted and safe to paste into an issue:

```bash
curl -s https://<your-host>/api/v1/system/diagnostics | python3 -m json.tool
```

## Deliberate limits

| Variable | Value | Why |
|---|---|---|
| `BIONANO_MAX_CONCURRENT_JOBS` | 1 | one OCPU is not four |
| `BIONANO_MAX_PRODUCTION_STEPS` | 20,000 | bounds a single request's cost |
| `BIONANO_JOB_WALL_CLOCK_LIMIT_S` | 600 | fail visibly rather than hang |
| `OPENMM_CPU_THREADS` | 2 | leaves headroom for the API to stay responsive |
| `BIONANO_RUNTIME_QUOTA_BYTES` | 8 GiB | jobs are refused before the disk fills |

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
