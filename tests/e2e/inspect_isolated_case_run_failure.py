"""Emit a fixed sanitized receipt for one failed strict standalone case run."""
import argparse
import json

from .support.isolated_case_run_failure_result import inspect_failed_isolated_case_run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--expected-case", required=True)
    parser.add_argument("--expected-revision", required=True)
    arguments = parser.parse_args()
    print(json.dumps(inspect_failed_isolated_case_run(
        arguments.private_root, arguments.expected_case, arguments.expected_revision),
        sort_keys=True))


if __name__ == "__main__":
    main()
