"""One-shot audit retention maintenance command for cron or a platform scheduler."""

from __future__ import annotations

import argparse
import json

from app.repositories.workspace_factory import workspace_repository
from app.services.maintenance import run_audit_retention, serialize_retention_runs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Nova audit retention maintenance.")
    parser.add_argument("--apply", action="store_true", help="Delete records beyond each workspace retention policy.")
    args = parser.parse_args()
    results = run_audit_retention(workspace_repository, dry_run=not args.apply)
    print(json.dumps({"dry_run": not args.apply, "results": serialize_retention_runs(results)}))


if __name__ == "__main__":
    main()
