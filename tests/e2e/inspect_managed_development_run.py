"""Correlate one passing managed development summary with terminal owned-host cleanup."""
import argparse
import json

from .support.managed_development_result import inspect_managed_development_run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_managed_development_run(args.session_dir, args.summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
