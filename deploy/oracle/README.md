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

## Known caveats

- **The tunnel URL is public and unauthenticated.** Unguessable, but anyone
  holding it can start simulations on your VM. The step and wall-clock caps
  above bound the damage; they do not prevent it.
- **Quick-tunnel URLs are not stable across restarts.** See the named-tunnel
  section.
- **Free-tier Oracle VMs can be reclaimed** if idle for long periods. Check it
  is still up before you rely on it.
