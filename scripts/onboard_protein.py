#!/usr/bin/env python3
"""COSMORA Protein Library Candidate Onboarding Wrapper Script."""

import sys
from pathlib import Path

# Add backend directory to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))

from app.cli.onboard_protein import (
    main,
)

if __name__ == "__main__":
    main()
