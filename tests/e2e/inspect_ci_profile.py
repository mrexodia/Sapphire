"""Inspect a private isolated-gate profile without starting services or accounts."""
import argparse
import json
import sys

from .support.ci_profile_result import inspect_ci_profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--worker")
    parser.add_argument("--binaries")
    args = parser.parse_args(argv)
    proof = inspect_ci_profile(args.profile, worker=args.worker, binaries=args.binaries)
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Isolated-gate private profile rejected: {error}", file=sys.stderr)
        sys.exit(1)
