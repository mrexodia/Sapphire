"""Correlate managed provisioning with its private profile and terminal owned host."""
import argparse
import json

from .support.managed_provisioning_result import inspect_managed_provisioning


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_managed_provisioning(
        args.session_dir, args.summary, args.profile), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
