#!/usr/bin/env python
"""Run one simulation end-to-end without the HTTP layer, and optionally freeze
the result as the labelled precomputed fallback.

    python scripts/run_demo_simulation.py                       # 1UBQ, rapid demo
    python scripts/run_demo_simulation.py --pdb-id 1PGA
    python scripts/run_demo_simulation.py --write-precomputed    # also freeze it

``--write-precomputed`` copies the finished metrics and structures into
``data/precomputed/<PDB_ID>/``. Anything served from there is labelled
"Precomputed OpenMM Result" throughout the API and UI - it is genuinely a real
OpenMM run, just not one performed on the viewer's machine, and it is never
presented as a live simulation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import warnings
from pathlib import Path
import sys

# scripts/ is not a package, so the shared console helper is imported by
# path. init_console() must run before any output is written.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import init_console  # noqa: E402

init_console()

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdb-id", default="1UBQ")
    parser.add_argument("--chain-id", default="A")
    parser.add_argument("--scenario-id", default="GCR_DEEP_SPACE_REFERENCE")
    parser.add_argument("--preset-id", default="rapid_demo")
    parser.add_argument("--temperature", type=float, default=300.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--write-precomputed",
        action="store_true",
        help="freeze the finished result into data/precomputed/<PDB_ID>/",
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    from app.core.logging import configure_logging
    from app.schemas.prediction import PredictionRequest
    from app.schemas.simulation import SimulationRequest
    from app.services import prediction_service, simulation_service
    from app.simulation.job_manager import get_job_manager

    configure_logging()

    print("BioNano-Sim demo run")
    print("=" * 74)
    print(
        f"protein={args.pdb_id} chain={args.chain_id} scenario={args.scenario_id} "
        f"preset={args.preset_id} T={args.temperature}K seed={args.seed}"
    )

    # --- 1. ML prediction first (the UI enforces the same order) --------
    print("\n[1] ML prediction")
    ml_percent = None
    prediction_id = None
    try:
        result = prediction_service.run_prediction(
            PredictionRequest(
                pdb_id=args.pdb_id,
                chain_id=args.chain_id,
                scenario_id=args.scenario_id,
                temperature_kelvin=args.temperature,
                random_seed=args.seed,
            )
        )
        ml_percent = result.degradation_percent
        prediction_id = result.prediction_id
        print(
            f"  {ml_percent:.3f} % ({result.risk_level}), model {result.model_version} "
            f"[{result.model_status}], confidence={result.confidence}"
        )
        print(f"  {len(result.warnings)} warning(s); first: {result.warnings[0][:100]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  no ML estimate: {exc}")

    # --- 2. Simulation ---------------------------------------------------
    print("\n[2] Simulation")
    job = simulation_service.submit_simulation(
        SimulationRequest(
            pdb_id=args.pdb_id,
            chain_id=args.chain_id,
            scenario_id=args.scenario_id,
            preset_id=args.preset_id,
            temperature_kelvin=args.temperature,
            random_seed=args.seed,
            ml_degradation_percent=ml_percent,
            prediction_id=prediction_id,
        )
    )
    job_id = job["job_id"]
    print(f"  job {job_id}")

    manager = get_job_manager()
    start = time.monotonic()
    last_stage = None
    while time.monotonic() - start < args.timeout:
        status = manager.read_status(job_id)
        stage = status.get("current_stage")
        if stage != last_stage:
            print(
                f"  [{time.monotonic() - start:6.1f}s] {status['status']:<9} {stage} "
                f"({status.get('progress', 0) * 100:.0f}%)"
            )
            last_stage = stage
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.5)
    else:
        print(f"  TIMEOUT after {args.timeout}s")
        return 1

    status = manager.read_status(job_id)
    if status["status"] != "completed":
        print(f"\n  job {status['status']}: {status.get('error_code')} - "
              f"{status.get('error_message')}")
        for line in (manager.detail(job_id)["log_tail"] or [])[-15:]:
            print("   ", line)
        return 1

    print(f"  completed in {status['duration_seconds']:.1f}s")

    # --- 3. Results ------------------------------------------------------
    print("\n[3] Results")
    results = simulation_service.job_results(job_id)
    metrics = results["metrics"]
    proxy = metrics.get("degradation_proxy", {})
    print(f"  label            : {results['result_label']}")
    print(f"  platform         : {results['metadata']['topology'].get('platform')}")
    print(f"  frames           : {metrics['n_frames']} over {metrics['simulated_time_ps']} ps")
    print(f"  final RMSD       : {metrics['rmsd_nm']['final']} nm")
    print(f"  mean RMSF        : {metrics['rmsf_nm']['mean']} nm")
    print(f"  Rg change        : {metrics['radius_of_gyration_nm']['relative_change']}")
    print(f"  mean temperature : {metrics['temperature_kelvin']['mean']} K")
    print(f"  drift proxy      : {proxy.get('percent')} % ({proxy.get('label')})")
    print(f"  stability        : {results['stability_summary']['verdict']}")
    comparison = results["comparison"]
    print(
        f"  ML vs simulation : ML {comparison['ml_degradation_percent']} % vs proxy "
        f"{comparison['simulation_degradation_proxy_percent']} % "
        f"(delta {comparison['difference_percentage_points']} pp, {comparison['agreement']})"
    )

    # --- 4. Freeze as precomputed fallback -------------------------------
    if args.write_precomputed:
        print("\n[4] Freezing as precomputed fallback")
        job_dir = manager.job_dir(job_id)
        dest = REPO / "data" / "precomputed" / args.pdb_id.upper()
        dest.mkdir(parents=True, exist_ok=True)

        payload = dict(results)
        payload["engine"] = "precomputed"
        payload["result_label"] = "Precomputed OpenMM Result"
        payload["job_id"] = f"precomputed-{args.pdb_id.upper()}"
        payload["provenance"] = {
            "origin": "scripts/run_demo_simulation.py --write-precomputed",
            "original_job_id": job_id,
            "generated_on": results["reproducibility"]
            .get("software", {})
            .get("platform"),
            "statement": (
                "This is a real OpenMM run, executed once and committed to the "
                "repository so the results interface stays demonstrable when a live "
                "run cannot complete on the viewer's machine. It is labelled "
                "'Precomputed OpenMM Result' everywhere it appears and is never "
                "presented as a live simulation."
            ),
        }
        (dest / "metrics.json").write_text(
            json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
        )
        for name in ("final.pdb", "input.pdb", "topology.pdb"):
            source = job_dir / name
            if source.exists():
                shutil.copy2(source, dest / name)
        analysis_dest = dest / "analysis"
        analysis_dest.mkdir(exist_ok=True)
        for csv in (job_dir / "analysis").glob("*.csv"):
            shutil.copy2(csv, analysis_dest / csv.name)
        print(f"  wrote {dest.relative_to(REPO)}")
        for item in sorted(dest.rglob("*")):
            if item.is_file():
                print(f"    {item.relative_to(dest)} ({item.stat().st_size:,} bytes)")

    print("\n" + "=" * 74)
    print(f"Done. Job {job_id}")
    print(f"  results : GET /api/v1/simulations/{job_id}/results")
    print(f"  report  : GET /api/v1/reports/{job_id}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
