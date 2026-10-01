"""Inspect one retained external provisioning→registry→placement chain."""
import argparse
import json
from pathlib import Path

from .support.development_placement_result import inspect_development_placement_chain


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--provisioning-summary", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--development-summary", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_development_placement_chain(
        args.profile, args.provisioning_summary, args.registry,
        args.development_summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
