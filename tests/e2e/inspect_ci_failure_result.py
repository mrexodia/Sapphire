"""Validate a failed sanitized gate summary before diagnostic publication."""
import argparse
import json
import sys

from .support.ci_failure_result import inspect_ci_failure_result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args(argv)
    proof = inspect_ci_failure_result(args.summary, args.expected_revision)
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Failed isolated-gate summary rejected: {error}", file=sys.stderr)
        sys.exit(1)
