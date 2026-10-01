"""Inspect exact private-profile association for an external shared run."""
import argparse
import json
from pathlib import Path

from .support.development_profile_result import inspect_development_profile_result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_development_profile_result(
        args.summary, args.profile), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
