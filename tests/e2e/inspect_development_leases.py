"""Inspect exact local bot leases without releasing them or contacting Sapphire."""
import argparse
import json
from pathlib import Path
import time

from .support.development_lease import inspect_account_leases


def run(profile, artifacts, *, lease_root=None):
    started = time.monotonic()
    report = inspect_account_leases(profile, lease_root)
    report["status"] = "inspected" if report["state"] in {"clear", "retained"} else "failed"
    if report["state"] == "retained":
        report["operator_note"] = "Both exact local leases identify one run; independently verify both bots offline before any manual recovery."
    elif report["state"] == "ambiguous":
        report["operator_note"] = "Partial, changed, unreadable or malformed exact lease state; do not release, reuse or reprovision either account."
    else:
        report["operator_note"] = "No exact local cooperating-runner lease was observed; this is not server-side offline proof."
    report["elapsed_seconds"] = time.monotonic() - started
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=False)
    (artifacts / "lease-inspection-summary.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Private two-account development profile")
    parser.add_argument("--artifacts", required=True, help="NEW private artifact directory")
    parser.add_argument("--lease-root", help="Override the local lease root (primarily for isolated tests)")
    args = parser.parse_args(argv)
    try:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        report = run(profile, args.artifacts, lease_root=args.lease_root)
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"status": "failed", "stage": "preflight", "error_type": type(error).__name__}))
        return 1
    print(json.dumps({"status": report["status"], "state": report["state"],
                      "scope": report["scope"], "artifacts": args.artifacts}))
    return 0 if report["status"] == "inspected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
