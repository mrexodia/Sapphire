"""Read-only verifier for a current development-enabled graphical guest result."""
import argparse
import json

from .support.client_result import inspect_client_development_result
from .support.client_snapshot import git
from .support.environment import REPO


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True,
                        help="private host-visible graphical output directory")
    args = parser.parse_args(argv)
    revision = git(REPO, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    print(json.dumps(inspect_client_development_result(args.output, revision), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
