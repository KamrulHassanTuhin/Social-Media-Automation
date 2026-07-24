from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from app.config.settings import get_settings
from app.integrations.base import IntegrationError, PublishResult, Publisher
from app.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig
from app.integrations.http import NuelinkPublisher


MASTER_DATA_START_ROW = 4
MAX_RETRIES = 3
UPDATED_BY = "sheet-automation"


@dataclass(frozen=True)
class SheetRow:
    row_number: int
    content_id: str
    topic: str
    automation_status: str
    publisher: str
    live_url: str
    media_link: str
    copies: dict[str, str]
    retry_count: int
    manual_retry: bool
    external_post_id: str


@dataclass(frozen=True)
class RowResult:
    content_id: str
    row_number: int
    status: str
    reason: str
    channels: int = 0


def _cell(row: list[Any], index: int) -> str:
    return str(row[index]).strip() if index < len(row) and row[index] is not None else ""


def _bool_cell(row: list[Any], index: int) -> bool:
    return _cell(row, index).lower() in {"true", "yes", "1"}


def _int_cell(row: list[Any], index: int) -> int:
    try:
        return max(0, int(float(_cell(row, index) or "0")))
    except ValueError:
        return 0


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _job_id(content_id: str, channel: str, retry_count: int) -> str:
    raw = f"{content_id}|{channel}|{retry_count}"
    return f"sheet-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def parse_master_rows(values: list[list[Any]]) -> list[SheetRow]:
    rows: list[SheetRow] = []
    for row_index, row in enumerate(values[1:], start=MASTER_DATA_START_ROW):
        topic = _cell(row, 0)
        if not topic:
            continue
        copies = {
            "facebook_instagram": _cell(row, 14),
            "linkedin": _cell(row, 15),
            "youtube": _cell(row, 16),
            "gbp": _cell(row, 17),
            "reddit": _cell(row, 18),
        }
        rows.append(SheetRow(
            row_number=row_index,
            content_id=_cell(row, 22),
            topic=topic,
            automation_status=_cell(row, 20),
            publisher=_cell(row, 21),
            live_url=_cell(row, 13),
            media_link=_cell(row, 19),
            copies=copies,
            retry_count=_int_cell(row, 30),
            manual_retry=_bool_cell(row, 32),
            external_post_id=_cell(row, 28),
        ))
    return rows


class SheetAutomationService:
    """Validates and publishes Sheet rows with dry-run and log safeguards."""

    required_channels = ("facebook_instagram", "linkedin", "gbp")

    def __init__(self, sheets: Any, publisher: Publisher, dry_run: bool = True, max_retries: int = MAX_RETRIES, now: Callable[[], datetime] | None = None) -> None:
        self.sheets = sheets
        self.publisher = publisher
        self.dry_run = dry_run
        self.max_retries = max_retries
        self.now = now or (lambda: datetime.now(timezone.utc))

    def run(self) -> dict[str, Any]:
        values = self.sheets.read_values(self.sheets.config.master_range)
        rows = parse_master_rows(values)
        log_values = self.sheets.read_values(self.sheets.config.log_range)
        successful_keys = self._successful_log_keys(log_values)
        results = [self._process(row, successful_keys) for row in rows]
        return {
            "status": "DRY_RUN" if self.dry_run else "COMPLETED",
            "dry_run": self.dry_run,
            "processed": len(results),
            "published": sum(result.status == "PUBLISHED" for result in results),
            "validated": sum(result.status == "DRY_RUN" for result in results),
            "failed": sum(result.status == "FAILED" for result in results),
            "skipped": sum(result.status == "SKIPPED" for result in results),
            "results": [result.__dict__ for result in results],
        }

    @staticmethod
    def _successful_log_keys(values: list[list[Any]]) -> set[tuple[str, str]]:
        successful: set[tuple[str, str]] = set()
        for row in values[1:]:
            content_id = _cell(row, 1)
            channel = _cell(row, 3).lower()
            action = _cell(row, 4).upper()
            status = _cell(row, 5).upper()
            if content_id and channel and action == "PUBLISH" and status == "SUCCEEDED":
                successful.add((content_id, channel))
        return successful

    def _process(self, row: SheetRow, successful_keys: set[tuple[str, str]]) -> RowResult:
        if not row.content_id:
            return self._record_failure(row, "MISSING_CONTENT_ID")
        if row.automation_status == "Published":
            return RowResult(row.content_id, row.row_number, "SKIPPED", "ALREADY_PUBLISHED")
        if row.automation_status not in {"Ready to Publish", "Scheduled"}:
            return RowResult(row.content_id, row.row_number, "SKIPPED", "NOT_READY")
        if row.external_post_id:
            return RowResult(row.content_id, row.row_number, "SKIPPED", "EXTERNAL_POST_ALREADY_RECORDED")
        if row.retry_count >= self.max_retries and not row.manual_retry:
            return self._record_failure(row, "RETRY_LIMIT_REACHED", status="Paused", log_status="SKIPPED")
        if row.publisher.upper() not in {"NUELINK", "NUELINK API"}:
            return self._record_failure(row, "PUBLISHER_NOT_SUPPORTED", status="Needs Review", log_status="SKIPPED")
        missing = self._missing(row)
        if missing:
            return self._record_failure(row, "MISSING_" + ",".join(missing), status="Needs Review")

        channels = [channel for channel, copy in row.copies.items() if copy and (row.content_id, channel) not in successful_keys]
        if not channels:
            return RowResult(row.content_id, row.row_number, "SKIPPED", "ALL_CHANNELS_ALREADY_SUCCEEDED")
        if self.dry_run:
            self._update_row(row, status=row.automation_status, job_id=_job_id(row.content_id, "dry-run", row.retry_count), external_id="", error=f"DRY_RUN_VALIDATED:{len(channels)} channels", retry_count=row.retry_count, platform="Nuelink")
            for channel in channels:
                self._append_log(row, channel, "DRY_RUN", "SUCCEEDED", _job_id(row.content_id, channel, row.retry_count), "", "DRY_RUN_VALIDATED")
            return RowResult(row.content_id, row.row_number, "DRY_RUN", "VALIDATED", len(channels))

        published = 0
        errors: list[str] = []
        for channel in channels:
            job_id = _job_id(row.content_id, channel, row.retry_count)
            try:
                result: PublishResult = self.publisher.publish(channel, row.topic, row.copies[channel], row.live_url)
                if result.manual_required or not result.external_post_id:
                    raise IntegrationError("Publisher returned a manual-required result.")
                published += 1
                successful_keys.add((row.content_id, channel))
                self._append_log(row, channel, "PUBLISH", "SUCCEEDED", job_id, result.external_post_id, "")
            except Exception as exc:  # noqa: BLE001 - one channel failure must not hide other results
                error = str(exc)[:500]
                errors.append(f"{channel}:{error}")
                self._append_log(row, channel, "PUBLISH", "FAILED", job_id, "", error)
        if errors:
            self._update_row(row, status="Failed", job_id=_job_id(row.content_id, "batch", row.retry_count), external_id="", error="; ".join(errors), retry_count=row.retry_count + 1, platform="Nuelink")
            return RowResult(row.content_id, row.row_number, "FAILED", "; ".join(errors), published)
        self._update_row(row, status="Published", job_id=_job_id(row.content_id, "batch", row.retry_count), external_id=f"{published}_CHANNELS", error="", retry_count=row.retry_count, platform="Nuelink")
        return RowResult(row.content_id, row.row_number, "PUBLISHED", "SUCCESS", published)

    def _missing(self, row: SheetRow) -> list[str]:
        missing: list[str] = []
        if not _valid_url(row.live_url):
            missing.append("LIVE_LINK")
        for channel in self.required_channels:
            if not row.copies.get(channel):
                missing.append(channel.upper())
        if not _valid_url(row.media_link):
            missing.append("MEDIA_LINK")
        return missing

    def _record_failure(self, row: SheetRow, reason: str, status: str = "Needs Review", log_status: str = "FAILED") -> RowResult:
        self._update_row(row, status=status, job_id="", external_id="", error=reason, retry_count=row.retry_count, platform="")
        self._append_log(row, "sheet", "VALIDATE", log_status, "", "", reason)
        return RowResult(row.content_id or "", row.row_number, "FAILED", reason)

    def _update_row(self, row: SheetRow, status: str, job_id: str, external_id: str, error: str, retry_count: int, platform: str) -> None:
        timestamp = self.now().isoformat()
        self.sheets.update_values(f"'Master View'!U{row.row_number}:U{row.row_number}", [[status]])
        self.sheets.update_values(f"'Master View'!AA{row.row_number}:AF{row.row_number}", [[platform, job_id, external_id, timestamp, retry_count, error]])
        self.sheets.update_values(f"'Master View'!AI{row.row_number}:AI{row.row_number}", [[UPDATED_BY]])

    def _append_log(self, row: SheetRow, channel: str, action: str, status: str, job_id: str, external_id: str, error: str) -> None:
        self.sheets.append_values(self.sheets.config.log_range, [
            self.now().isoformat(), row.content_id, row.topic, channel, action, status, job_id, external_id, "", row.retry_count, error, self.dry_run,
        ])


def build_sheet_automation() -> SheetAutomationService:
    settings = get_settings()
    if not settings.google_sheets_spreadsheet_id or not settings.google_sheets_service_account_json:
        raise IntegrationError("Google Sheets automation is not configured.")
    sheets = GoogleSheetsClient(GoogleSheetsConfig(
        spreadsheet_id=settings.google_sheets_spreadsheet_id,
        service_account_json=settings.google_sheets_service_account_json,
        master_range=settings.google_sheets_master_range,
        log_range=settings.google_sheets_log_range,
    ))
    publisher: Publisher
    if settings.nuelink_api_key:
        publisher = NuelinkPublisher(settings.nuelink_api_key, settings.nuelink_base_url, settings.nuelink_destination_id)
    else:
        raise IntegrationError("NUELINK_API_KEY is required for Sheet publishing automation.")
    return SheetAutomationService(sheets, publisher, settings.sheet_automation_dry_run, settings.sheet_automation_max_retries)


def run_sheet_automation() -> dict[str, Any]:
    try:
        return build_sheet_automation().run()
    except IntegrationError as exc:
        return {"status": "NOT_CONFIGURED", "dry_run": True, "processed": 0, "published": 0, "validated": 0, "failed": 0, "skipped": 0, "results": [], "reason": str(exc)}
