"""Run one bot scenario against the running dev stack and watch it in game.

    python -m tests.e2e.scenario say_and_walk --profile .e2e-dev.json
    python -m tests.e2e.scenario --list

The bots stay logged in after the scenario until you press Ctrl+C, so you can
look at them from your own character. Bot accounts are named bot_* and are
removed with --purge (or by the next pytest session).
"""
import argparse
import sys
import time

from .scenarios import SCENARIOS, logout_all
from .support.devserver import DevServer, SetupError, load_profile
from .support.worker import Worker, WorkerError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", nargs="?", help="scenario name (see --list)")
    parser.add_argument("--profile", help="profile JSON pointing at the running dev stack")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    parser.add_argument("--no-hold", action="store_true", help="log the bots out as soon as the scenario is done")
    parser.add_argument("--purge", action="store_true", help="delete offline bot_* accounts first")
    args = parser.parse_args(argv)

    if args.list or not args.name:
        for name, fn in SCENARIOS.items():
            print(f"{name:16} {fn.__doc__.strip() if fn.__doc__ else ''}")
        return 0
    if args.name not in SCENARIOS:
        parser.error(f"unknown scenario {args.name!r}; use --list")
    if not args.profile:
        parser.error("--profile is required")

    def log(line):
        print(time.strftime("%H:%M:%S"), line, flush=True)

    try:
        server = DevServer(load_profile(args.profile))
        server.check_alive()
        if args.purge:
            summary = server.purge_bots()
            log(f"purged {summary['deleted_accounts']} bot accounts")
        with Worker(server.worker, server.artifacts / args.name, server.deadline_scale) as worker:
            bots = SCENARIOS[args.name](server, worker, log)
            log(f"scenario {args.name} complete; worker journals in {worker.artifacts}")
            if not args.no_hold:
                log("bots are standing in the world; press Ctrl+C to log them out")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    log("logging out")
            logout_all(bots)
            log("bots logged out")
        return 0
    except (SetupError, WorkerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
