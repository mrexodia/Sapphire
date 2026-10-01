"""Explicitly launch one prepared Windows Sandbox and retain bounded disposal evidence."""
from __future__ import annotations

import argparse
import json

from .support.client_disposal import approve_disposal, run_prepared_sandbox


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    launch = modes.add_parser("launch", help="Launch exact run.wsb; close and confirm discard before timeout")
    launch.add_argument("--prepared", required=True)
    launch.add_argument("--timeout-seconds", type=int, default=1800)
    approve = modes.add_parser("approve-disposal", help="ONLY after confirming the owned discard dialog")
    approve.add_argument("--prepared", required=True)
    approve.add_argument("--confirmed-owned-discard", action="store_true", required=True)
    args = parser.parse_args(argv)
    value = (run_prepared_sandbox(args.prepared, args.timeout_seconds)
             if args.mode == "launch" else approve_disposal(args.prepared))
    print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
