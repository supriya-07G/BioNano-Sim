# syntax=docker/dockerfile:1
#
# Single-image deployment: the Vite build is served by FastAPI from the same
# origin as the API. That is what lets the frontend keep VITE_API_BASE_URL
# empty and call a relative /api/v1, so CORS never enters the picture.
#
# Targeted at a free Hugging Face Space (Docker SDK, CPU basic). See
# docs/DEPLOYMENT.md.

# --- Stage 1: build the frontend ---------------------------------------------
FROM node:22-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

# The 3Dmol bundle is vendored, not an npm dependency, and is gitignored -- so
# it is absent from a clean checkout and the structure viewer would silently
# render nothing. Fetch it here, and fail the build if it cannot be had rather
# than shipping an image whose 3D panels are blank.
ADD https://3dmol.org/build/3Dmol-min.js /build/public/vendor/3Dmol-min.js
RUN test -s /build/public/vendor/3Dmol-min.js     && echo "3Dmol bundle: $(wc -c < /build/public/vendor/3Dmol-min.js) bytes"

RUN npm run build

# --- Stage 2: runtime ---------------------------------------------------------
FROM python:3.11-slim AS runtime

# OpenMM's manylinux wheel links against libgomp, which slim does not ship.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Spaces runs the container as uid 1000.
RUN useradd -m -u 1000 user

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so an app-only edit does not reinstall OpenMM.
COPY backend/requirements.txt backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r backend/requirements.txt

# config.py derives every path from the repo root (backend/app -> backend ->
# /app), so data/ and models/ must sit beside backend/ exactly as in the repo.
COPY backend/ backend/
COPY data/ data/
COPY models/ models/
COPY scripts/ scripts/
COPY --from=frontend /build/dist backend/app/static

# runtime/ is rewritten on every job. On a free Space the filesystem is
# ephemeral regardless, and /tmp is the only guaranteed-writable path.
ENV BIONANO_RUNTIME_DIR=/tmp/bionano-runtime

# A free Space has 2 vCPU. The local 50k-step ceiling would take many minutes
# there and read as a hang, so the hosted demo is capped well below it. These
# are environment overrides, not code changes -- a local run is unaffected.
ENV BIONANO_MAX_PRODUCTION_STEPS=5000 \
    BIONANO_JOB_WALL_CLOCK_LIMIT_S=240

RUN chown -R user:user /app
USER user

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "backend"]
