"""Inspect retained external shared-server provisioning evidence read-only."""
import argparse
import json
from pathlib import Path

from .support.development_provisioning_result import inspect_development_provisioning


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_development_provisioning(args.summary, args.profile), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
