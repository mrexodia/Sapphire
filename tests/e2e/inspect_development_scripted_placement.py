"""Inspect scripted local publication plus external received placement evidence."""
import argparse
import json
from pathlib import Path

from .support.development_scripted_placement_result import (
    inspect_development_scripted_placement)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--provisioning-summary", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--operator-artifact-dir", type=Path, required=True)
    parser.add_argument("--development-summary", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_development_scripted_placement(
        args.profile, args.provisioning_summary, args.registry,
        args.operator_artifact_dir, args.development_summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
