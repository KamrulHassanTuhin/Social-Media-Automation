"""Development worker entrypoint.

Production should replace the in-memory queue with claims against `job_queue`
and run this process separately from the API web service.
"""

from __future__ import annotations

import time

from app.jobs.outbox import notification_outbox
from app.jobs.publishing import publishing_store
from app.jobs.queue import job_queue
from app.jobs.worker import JobWorker
from app.repositories.factory import content_repository


def main() -> None:
    worker = JobWorker(job_queue, notification_outbox, content_repository, publishing_store)
    while True:
        worker.run_once()
        time.sleep(1)


if __name__ == "__main__":
    main()
