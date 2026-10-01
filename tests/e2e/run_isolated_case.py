"""Run and inspect one allowlisted isolated E2E case in a fresh private root."""
import argparse
import sys

from .support.isolated_case_runner import run_isolated_case


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--expected-case", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--worker")
    parser.add_argument("--binaries")
    args = parser.parse_args(argv)
    try:
        code = run_isolated_case(
            args.profile, args.private_root, args.expected_case,
            args.expected_revision, worker=args.worker, binaries=args.binaries)
    except BaseException:
        code = 1
    print("Standalone isolated case accepted." if code == 0
          else "Standalone isolated case failed; inspect the private root.")
    return code


if __name__ == "__main__":
    sys.exit(main())
