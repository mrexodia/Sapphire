"""Inspect one retained standalone isolated owned-world fault artifact."""
import argparse
import json
import sys

from .support.isolated_fault_result import inspect_isolated_fault


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args(argv)
    proof = inspect_isolated_fault(args.artifact_dir, args.expected_revision)
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Isolated owned-world fault evidence rejected: {error}", file=sys.stderr)
        sys.exit(1)
