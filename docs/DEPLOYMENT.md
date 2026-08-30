# Deploying BioNano-Sim

The whole app ships as one Docker image: FastAPI serves the API *and* the built
Vite frontend from the same origin. That is why `VITE_API_BASE_URL` is left
empty — the frontend calls a relative `/api/v1`, so there is no CORS
configuration and no second service to keep in sync.

## Free hosting: Hugging Face Spaces

Spaces is the only free tier that fits this app. OpenMM 8.6 is a runtime
dependency (`backend/requirements.txt`), which makes the image roughly 2 GB —
too large for Render's free 512 MB dyno, and impossible on Vercel or Netlify
functions (250 MB limit, short timeouts). A free CPU Space gives 2 vCPU and
16 GB RAM with no payment method.

### Steps

1. Create the Space at <https://huggingface.co/new-space>:
   - **SDK:** Docker → *Blank*
   - **Hardware:** CPU basic (free)
   - **Visibility:** Public (free tier requires it)

2. Create a Hugging Face access token with **write** scope:
   Hugging Face → Settings → Access Tokens → *New token*.

3. Wire GitHub up to deploy for you. In the GitHub repo, under
   **Settings → Secrets and variables → Actions**:

   | Kind | Name | Value |
   |---|---|---|
   | Secret | `HF_TOKEN` | the write token from step 2 |
   | Variable | `HF_USERNAME` | your Hugging Face username |
   | Variable | `HF_SPACE` | the Space name, e.g. `BioNano-Sim` |

4. Push to `main`. The `deploy-space` workflow mirrors the repository to the
   Space on every push, so GitHub stays the only place you push to. You can
   also trigger it by hand from **Actions → deploy-space → Run workflow**.

5. Watch the Space's **Logs** tab. The first build takes 10–15 minutes, most of
   it installing OpenMM. Later pushes reuse the layer cache and take 2–3
   minutes.

### Pushing to the Space by hand

The Action is just a `git push`, so you can do the same thing locally if you
would rather not wait for CI:

```bash
git remote add space https://huggingface.co/spaces/<your-username>/BioNano-Sim
git push space main
```

Use your Hugging Face username and the write token as the password.

The Space configuration lives in the YAML frontmatter at the top of
`README.md` (`sdk: docker`, `app_port: 7860`). Do not delete that block — the
Space repo's README *is* this file, and without it the Space will not start.

## What the hosted build changes

The Dockerfile sets three environment overrides. No code differs between local
and hosted.

| Variable | Hosted | Why |
|---|---|---|
| `BIONANO_RUNTIME_DIR` | `/tmp/bionano-runtime` | The only guaranteed-writable path in the container. |
| `BIONANO_MAX_PRODUCTION_STEPS` | `5000` (local: 50,000) | Two shared vCPUs. A 50k-step run takes many minutes and reads as a hang. |
| `BIONANO_JOB_WALL_CLOCK_LIMIT_S` | `240` (local: 900) | Fail visibly rather than tie up the single job slot. |

## Known limits of the free tier

- **Spaces sleep after ~48 h idle.** The first request then takes about a
  minute to wake the container. Open the URL a few minutes before a demo.
- **The filesystem is ephemeral.** Completed jobs in `runtime/` do not survive
  a restart. Anything that must persist belongs in `data/` or `models/`, which
  are baked into the image.
- **One job at a time** (`max_concurrent_jobs = 1`). Concurrent visitors queue.

## Local check before pushing

```bash
docker build -t bionano-sim .
docker run --rm -p 7860:7860 bionano-sim
```

Then open <http://localhost:7860>. The frontend should load at `/`, the API
docs at `/docs`, and `/api/v1/system/readiness` should report OpenMM available.

## Paid alternatives

If sleeping is unacceptable, Railway (~$5 credit) and Fly.io both run this
image without changes. Render works from its $7/month instance; the free tier
does not have the memory.
