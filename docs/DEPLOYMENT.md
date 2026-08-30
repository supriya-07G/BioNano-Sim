# Deploying BioNano-Sim

Three ways to show this app, in increasing order of effort. Pick the cheapest
one that meets the need.

| | Setup | Public URL | Survives your laptop closing | Use when |
|---|---|---|---|---|
| **localhost** | already done | no | no | presenting in person |
| **Cloudflare tunnel** | ~3 min | yes, temporary | no | someone remote needs to look now |
| **GitHub Codespace** | ~4 min | yes, while running | no (idle timeout) | a free HTTPS URL with no VM and no card |
| **Vercel + Oracle VM** | a few hours | yes, permanent | yes | a link that outlives the demo |

No Docker is required for any of them, and the permanent setup offers it as a
choice rather than a requirement: the API runs either under Docker Compose or
directly under systemd. See
[deploy/oracle/README.md](../deploy/oracle/README.md).

> **Hugging Face Spaces is not an option.** Docker and Gradio Spaces require a
> paid PRO plan — *"Static Spaces stay free for everyone"* — and a Static Space
> serves files, not compute, so it cannot run OpenMM.

---

## Running it locally

Two terminals:

```bash
cd backend && ../.venv311/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm run dev
```

- Dashboard: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>

Vite proxies `/api` to the backend, so the frontend calls a relative
`/api/v1` and there is no CORS configuration in the local path at all.

## GitHub Codespaces

A free HTTPS URL with no VM, no card and no capacity lottery. This repo ships
a devcontainer, so a Codespace boots with dependencies installed, structures
fetched and the 3Dmol bundle in place.

1. On the repo: **Code → Codespaces → Create codespace on main**
2. Wait for setup (~4 minutes; it prints a banner when done)
3. Start the two servers exactly as above, but with `.venv311/bin/python`
4. **PORTS** tab → right-click **5173** → **Port Visibility → Public**
5. Copy the `https://<name>-5173.app.github.dev` URL

Forwarding 5173 alone is enough: Vite proxies `/api` to the backend inside the
Codespace, so one URL serves the whole app with no CORS. Vite's host check
already allows `.app.github.dev`, so there is no "Blocked request" step.

**Limits.** 120 core-hours and 15 GB storage per month on a free account, so
roughly 60 hours on a 2-core machine. It stops after 30 minutes idle by
default — raise that under Settings → Codespaces → Default idle timeout. A
stopped Codespace's URL errors until it is restarted.

**GitHub Actions cannot host this.** Running a server in a workflow and
tunnelling out of it violates the Acceptable Use Policies, which prohibit
using Actions for activity unrelated to building, testing or deploying the
project. Accounts are suspended for it. GitHub Pages is static-only: it could
host the frontend build, but not OpenMM.

## Sharing localhost through a Cloudflare tunnel

The fastest way to give someone a working link. No account required.

```bash
winget install --id Cloudflare.cloudflared
```

With both servers running, point a tunnel at the **frontend** port:

```bash
cloudflared tunnel --url http://localhost:5173
```

It prints a `https://<random>.trycloudflare.com` URL. Tunnelling 5173 rather
than 8000 is deliberate: Vite proxies `/api` to the backend, so one tunnel
serves the whole app.

**Vite will reject the tunnel URL** unless its hostname is allowed — you get a
bare "Blocked request" page. Restart the frontend with it:

```bash
$env:VITE_ALLOWED_HOSTS="<random>.trycloudflare.com"; npm run dev
```

Hostname only: no `https://`, no trailing slash.

### What a tunnel is and is not

- It exposes **your machine**. It stops when you close the terminal.
- The URL is unguessable but **not authenticated**. Anyone holding it can start
  simulations on your hardware. Share it narrowly and stop the tunnel after.
- It serves the **dev build**, so it is slower than a production build.

## Permanent: Vercel frontend + Oracle backend

React on a CDN, the API on a VM with real memory, HTTPS between them with no
domain purchased. Full runbook, including the systemd units, the Caddy TLS
setup and auto-deploy from GitHub:
**[deploy/oracle/README.md](../deploy/oracle/README.md)**.

The two things that silently break this setup are worth repeating here:

1. **`VITE_API_BASE_URL` is the origin only** — no `/api/v1`.
   `frontend/src/services/api.ts` appends `/api/v1` itself, so including it
   produces `/api/v1/api/v1/...` and every request 404s.
2. **Vite bakes environment variables in at build time.** A variable added
   after a deploy does nothing until the next one.

## Configuration

Every setting is an environment variable with a `BIONANO_` prefix.

| Variable | Default | Purpose |
|---|---|---|
| `BIONANO_CORS_ORIGINS` | localhost dev ports | comma-separated origins allowed to call the API |
| `BIONANO_RUNTIME_DIR` | `<repo>/runtime` | where jobs, uploads and reports are written |
| `BIONANO_MAX_CONCURRENT_JOBS` | 1 | simultaneous simulations |
| `BIONANO_MAX_PRODUCTION_STEPS` | 50,000 | ceiling on a single run |
| `BIONANO_JOB_WALL_CLOCK_LIMIT_S` | 900 | fail visibly rather than hang |
| `BIONANO_RUNTIME_QUOTA_BYTES` | 8 GiB | storage ceiling before jobs are refused |
| `BIONANO_MIN_FREE_DISK_BYTES` | 2 GiB | refuse to start below this |
| `VITE_API_BASE_URL` | empty (same origin) | backend origin for the frontend build |
| `VITE_ALLOWED_HOSTS` | — | extra hostnames the dev server accepts |
