"""Modal deployment entrypoint for the Nova API and background worker.

Run from the repository root after installing and authenticating the Modal CLI:

    modal deploy infrastructure/modal/modal_app.py

The deployed API is exposed at a Modal-generated ``*.modal.run`` URL. Runtime
configuration is injected from the ``nova-runtime`` Modal Secret so no
credentials are committed to the repository.
"""

from __future__ import annotations

import sys
from pathlib import Path

import modal


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


modal_app = modal.App("nova-content-studio")
# Modal CLI discovers the application through the conventional ``app`` name.
app = modal_app
runtime_secret = modal.Secret.from_name("nova-runtime")

api_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(API_ROOT / "requirements.txt"))
    .add_local_python_source("app", copy=True)
)


@modal_app.function(
    image=api_image,
    secrets=[runtime_secret],
)
@modal.asgi_app()
def api():
    from app.main import app

    return app


@modal_app.function(
    image=api_image,
    secrets=[runtime_secret],
    schedule=modal.Period(seconds=15),
    timeout=120,
)
def worker_tick() -> dict[str, str | bool | None]:
    """Process one queued job on each scheduled invocation."""

    from app.jobs.outbox import notification_outbox
    from app.jobs.publishing import publishing_store
    from app.jobs.queue import job_queue
    from app.jobs.worker import JobWorker
    from app.repositories.factory import content_repository

    worker = JobWorker(job_queue, notification_outbox, content_repository, publishing_store)
    job = worker.run_once()
    return {
        "processed": bool(job),
        "job_id": job.id if job else None,
        "status": job.status if job else None,
    }


@modal_app.local_entrypoint()
def main() -> None:
    print("Deploy with: modal deploy infrastructure/modal/modal_app.py")
