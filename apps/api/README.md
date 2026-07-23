# Nova Content API

FastAPI boundary for authentication, authorization, content services, jobs, and provider adapters. The API exposes health endpoints and versioned routes under `/api/v1` with the response contract from the master specification.

Run the local worker separately with `python worker.py` from this directory. It uses the in-memory queue for development; production must replace queue claims with the `job_queue` table or a Redis-backed worker.
