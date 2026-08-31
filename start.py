#!/usr/bin/env python3
"""COSMORA One-Step Launcher

Cross-platform single-command runner for COSMORA.
Automatically sets up environments, installs dependencies, fetches structure data,
starts both backend (Uvicorn) and frontend (Vite), and opens the web application in your browser.

Usage:
    python start.py
    npm start         (via root package.json)
    ./start.sh        (Linux/macOS)
    start.bat         (Windows)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def log(msg: str, symbol: str = "🚀") -> None:
    print(f"\n{symbol}  \033[1;36m[COSMORA]\033[0m {msg}", flush=True)


def check_and_install_backend() -> None:
    log("Checking Python backend dependencies...", "🐍")
    req_file = BACKEND_DIR / "requirements.txt"
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)]
        )
        print("  ✓ Backend dependencies verified.")
    except subprocess.CalledProcessError as exc:
        print(f"  ❌ Failed to install backend dependencies: {exc}")
        sys.exit(1)

    log("Checking local PDB structures and runtime directories...", "🧬")
    setup_script = ROOT / "scripts" / "setup_local.py"
    try:
        subprocess.check_call([sys.executable, str(setup_script)])
    except subprocess.CalledProcessError as exc:
        print(f"  ⚠️ Setup warning: {exc}")


def check_and_install_frontend() -> None:
    log("Checking Node frontend dependencies...", "⚡")
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("  Installing frontend packages via npm install (first run)...")
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        try:
            subprocess.check_call([npm_cmd, "install"], cwd=str(FRONTEND_DIR))
            print("  ✓ Frontend packages installed.")
        except subprocess.CalledProcessError as exc:
            print(f"  ❌ Failed to run npm install in frontend: {exc}")
            sys.exit(1)
    else:
        print("  ✓ Frontend dependencies verified.")


def main() -> None:
    print("\n=======================================================")
    print("      COSMORA — Protein Nanomachinery Stress Testing   ")
    print("=======================================================")

    check_and_install_backend()
    check_and_install_frontend()

    log("Starting Backend API Server (http://127.0.0.1:8000)...", "⚙️")
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    backend_proc = subprocess.Popen(backend_cmd, cwd=str(BACKEND_DIR))

    log("Starting Frontend Web Application (http://localhost:5173)...", "🌐")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev"]
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(FRONTEND_DIR))

    # Give servers 2 seconds to initialize before launching browser
    time.sleep(2.5)

    log("Opening COSMORA Web App in your default browser...", "✨")
    webbrowser.open("http://localhost:5173")

    print("\n" + "=" * 55)
    print("  COSMORA is live!")
    print("  • Frontend: http://localhost:5173")
    print("  • Backend:  http://127.0.0.1:8000/docs")
    print("  Press Ctrl+C anytime to stop both servers.")
    print("=" * 55 + "\n")

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        log("Shutting down COSMORA servers gracefully...", "🛑")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
            frontend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
            frontend_proc.kill()
        log("COSMORA stopped cleanly. Goodbye!", "👋")


if __name__ == "__main__":
    main()
