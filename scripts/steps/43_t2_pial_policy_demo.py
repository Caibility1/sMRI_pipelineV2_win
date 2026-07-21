#!/usr/bin/env python3
"""Decide whether a T2 sidecar describes a suitable recon-all pial input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def is_t2_pial_candidate(metadata):
    """Use only true 3D acquisitions for FreeSurfer's T2-guided pial refinement."""
    return str(metadata.get("MRAcquisitionType", "")).strip().upper() == "3D"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("sidecar")
    args = parser.parse_args(argv)
    sidecar = Path(args.sidecar)
    try:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"T2pial disabled: cannot read {sidecar}: {exc}", file=sys.stderr)
        return 1
    if is_t2_pial_candidate(metadata):
        print("T2pial enabled: 3D T2 acquisition")
        return 0
    acquisition = metadata.get("MRAcquisitionType", "unknown")
    thickness = metadata.get("SliceThickness", "unknown")
    spacing = metadata.get("SpacingBetweenSlices", "unknown")
    print(
        "T2pial disabled: "
        f"acquisition={acquisition}, slice_thickness={thickness}, spacing={spacing}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
