"""Strictly inspect one sanitized current isolated-gate public summary."""
import argparse
import json

from .support.ci_result import inspect_ci_result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_ci_result(args.summary, args.expected_revision), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
