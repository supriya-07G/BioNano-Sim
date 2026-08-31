"""CLI utility for curated protein candidate onboarding."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path if running as script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.schemas.onboarding import CandidateReviewAction, CandidateSubmission
from app.services import protein_onboarding_service


def main() -> None:
    parser = argparse.ArgumentParser(
        description="COSMORA Protein Library Onboarding Workflow CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Submit command
    submit_p = subparsers.add_parser("submit", help="Submit a PDB candidate for onboarding review.")
    submit_p.add_argument("--file", "-f", required=True, type=Path, help="Path to input .pdb file.")
    submit_p.add_argument("--pdb-id", "-i", required=True, help="Unique PDB ID or candidate ID.")
    submit_p.add_argument("--name", "-n", required=True, help="Descriptive protein name.")
    submit_p.add_argument("--uniprot", "-u", default="N/A", help="UniProt accession ID.")
    submit_p.add_argument("--role", "-r", required=True, help="Proposed mechanical role.")
    submit_p.add_argument("--reason", "-w", required=True, help="Selection rationale.")
    submit_p.add_argument("--chain", "-c", default="A", help="Target chain ID (default: A).")
    submit_p.add_argument("--source", default="RCSB PDB", help="Structure source.")
    submit_p.add_argument("--license", default="CC0 1.0 Universal", help="License note.")

    # List command
    list_p = subparsers.add_parser("list", help="List candidates in the onboarding queue.")
    list_p.add_argument(
        "--state", "-s", choices=["pending", "approved", "rejected"], help="Filter by review state."
    )

    # Review command
    review_p = subparsers.add_parser("review", help="Review and approve/reject a candidate.")
    review_p.add_argument("--candidate-id", "-i", required=True, help="Candidate ID.")
    review_p.add_argument("--action", "-a", choices=["approve", "reject"], required=True, help="Decision.")
    review_p.add_argument("--reviewer", "-r", required=True, help="Reviewer handle.")
    review_p.add_argument("--notes", "-m", default="", help="Review feedback notes.")

    args = parser.parse_args()

    if args.command == "submit":
        path: Path = args.file
        if not path.exists():
            print(f"Error: PDB file not found at '{path}'", file=sys.stderr)
            sys.exit(1)

        submission = CandidateSubmission(
            pdb_id=args.pdb_id,
            name=args.name,
            uniprot=args.uniprot,
            proposed_role=args.role,
            why_selected=args.reason,
            chain_id=args.chain,
            source=args.source,
            license_note=args.license,
        )
        try:
            record = protein_onboarding_service.submit_candidate(path.read_bytes(), submission)
            print(f"SUCCESS: Submitted candidate '{record['candidate_id']}' for review.")
            print(f"Status: {record['review_state']} | Length: {record['protein_length']} aa | SHA256: {record['sha256_structure_hash'][:12]}...")
        except Exception as err:
            print(f"FAILED: Candidate submission rejected: {err}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        candidates = protein_onboarding_service.list_candidates(args.state)
        print(f"Found {len(candidates)} candidate(s)" + (f" in state '{args.state}'" if args.state else "") + ":")
        for c in candidates:
            print(f" - [{c['review_state'].upper()}] {c['candidate_id']}: {c['name']} (Chain {c['chain_id']}, {c['protein_length']} aa)")

    elif args.command == "review":
        action = CandidateReviewAction(
            candidate_id=args.candidate_id,
            action=args.action,
            reviewer=args.reviewer,
            notes=args.notes,
        )
        try:
            record = protein_onboarding_service.review_candidate(action)
            print(f"SUCCESS: Candidate '{record['candidate_id']}' updated to status '{record['review_state'].upper()}' by {record['reviewed_by']}.")
        except Exception as err:
            print(f"FAILED: Review action failed: {err}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
