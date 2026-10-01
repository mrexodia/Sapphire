"""Inspect one retained standalone allowlisted isolated-case result."""
import argparse
import json
import sys

from .support.isolated_case_result import inspect_isolated_case


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--junit", required=True)
    parser.add_argument("--pytest-log", required=True)
    parser.add_argument("--expected-case", required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args(argv)
    proof = inspect_isolated_case(args.artifact_dir, args.junit, args.pytest_log,
                                  args.expected_case, args.expected_revision)
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Standalone isolated-case evidence rejected: {error}", file=sys.stderr)
        sys.exit(1)
