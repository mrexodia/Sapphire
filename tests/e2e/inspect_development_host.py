"""Read-only inspection of one terminal owned warm-development host session."""
import argparse
import json

from .support.development_host_result import inspect_owned_development_host


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_owned_development_host(args.session_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
