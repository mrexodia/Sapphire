"""Read-only verification of current graphical evidence plus explicit Sandbox disposal."""
from __future__ import annotations

import argparse
import json

from .support.client_disposal import inspect_completed_sandbox
from .support.client_snapshot import git
from .support.environment import REPO


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True)
    args = parser.parse_args(argv)
    revision = git(REPO, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    print(json.dumps(inspect_completed_sandbox(args.prepared, revision), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
