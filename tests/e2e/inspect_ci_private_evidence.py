"""Correlate one current public gate result with retained private per-case evidence."""
import argparse
import json

from .support.ci_private_result import inspect_ci_private_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--private-run-dir", required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_ci_private_evidence(
        args.summary, args.private_run_dir, args.expected_revision), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
