"""Reinspect one strict standalone private run and emit a sanitized receipt."""
import argparse
import json
import sys

from .support.isolated_case_run_result import inspect_isolated_case_run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--expected-case", required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args(argv)
    try:
        proof = inspect_isolated_case_run(
            args.private_root, args.expected_case, args.expected_revision)
        print(json.dumps(proof, indent=2))
        return 0
    except Exception as error:
        print(f"Standalone isolated-case run rejected: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
