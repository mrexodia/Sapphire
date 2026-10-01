"""Stage and remove one service-free fixture from a private isolated-gate profile."""
import argparse
import json
import sys

from .support.ci_staging_result import stage_ci_profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--private-artifacts", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--worker")
    parser.add_argument("--binaries")
    args = parser.parse_args(argv)
    proof = stage_ci_profile(args.profile, args.private_artifacts, args.expected_revision,
                             worker=args.worker, binaries=args.binaries)
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Isolated-gate service-free staging rejected: {error}", file=sys.stderr)
        sys.exit(1)
