"""Inspect two scripted local administrative placement publications."""
import argparse
import json
from pathlib import Path

from .support.development_operator_result import inspect_development_operator_publications


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_development_operator_publications(
        args.registry, args.artifact_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
