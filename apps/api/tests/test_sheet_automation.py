from __future__ import annotations

from datetime import datetime, timezone

from app.integrations.base import PublishResult, Publisher
from app.integrations.google_sheets import GoogleSheetsConfig
from app.services.sheet_automation import SheetAutomationService, parse_master_rows


class FakeSheets:
    def __init__(self, rows: list[list[object]], logs: list[list[object]] | None = None) -> None:
        self.config = GoogleSheetsConfig("sheet", "{}", "Master", "Log")
        self.rows = rows
        self.logs = logs or [["Timestamp", "Content ID", "Topic", "Platform", "Action", "Status"]]
        self.updates: list[tuple[str, list[list[object]]]] = []
        self.appended: list[list[object]] = []

    def read_values(self, range_name: str) -> list[list[object]]:
        return self.rows if range_name == "Master" else self.logs

    def update_values(self, range_name: str, values: list[list[object]]) -> None:
        self.updates.append((range_name, values))

    def append_values(self, range_name: str, values: list[object]) -> None:
        self.appended.append(values)


class FakePublisher(Publisher):
    name = "FAKE"

    def __init__(self, fail_channel: str | None = None) -> None:
        self.fail_channel = fail_channel
        self.calls: list[str] = []

    def publish(self, channel: str, topic: str, copy: str, live_url: str | None) -> PublishResult:
        self.calls.append(channel)
        if channel == self.fail_channel:
            raise RuntimeError("temporary provider failure")
        return PublishResult(self.name, channel, f"post-{channel}", f"https://example.test/post-{channel}")


def master_row(status: str = "Ready to Publish", content_id: str = "AC-0001") -> list[object]:
    row = [""] * 35
    row[0] = "CRM implementation checklist"
    row[13] = "https://axisconsulting.io/crm-checklist"
    row[14] = "Facebook copy"
    row[15] = "LinkedIn copy"
    row[17] = "GBP copy"
    row[19] = "https://cdn.example.test/image.png"
    row[20] = status
    row[21] = "Nuelink"
    row[22] = content_id
    return row


def test_parse_master_rows_uses_sheet_column_positions() -> None:
    rows = parse_master_rows([["header"], master_row()])
    assert rows[0].row_number == 4
    assert rows[0].content_id == "AC-0001"
    assert rows[0].copies["linkedin"] == "LinkedIn copy"


def test_dry_run_validates_and_logs_without_publishing() -> None:
    sheets = FakeSheets([["header"], master_row()])
    publisher = FakePublisher()
    service = SheetAutomationService(sheets, publisher, dry_run=True, now=lambda: datetime(2026, 7, 24, tzinfo=timezone.utc))

    result = service.run()

    assert result["status"] == "DRY_RUN"
    assert result["validated"] == 1
    assert publisher.calls == []
    assert len(sheets.appended) == 3


def test_missing_live_link_is_blocked() -> None:
    row = master_row()
    row[13] = ""
    sheets = FakeSheets([["header"], row])
    result = SheetAutomationService(sheets, FakePublisher(), dry_run=True).run()

    assert result["failed"] == 1
    assert "LIVE_LINK" in result["results"][0]["reason"]


def test_publish_is_idempotent_from_log_and_records_success() -> None:
    logs = [["Timestamp", "Content ID", "Topic", "Platform", "Action", "Status"], ["", "AC-0001", "", "linkedin", "PUBLISH", "SUCCEEDED"]]
    sheets = FakeSheets([["header"], master_row()], logs)
    publisher = FakePublisher()
    result = SheetAutomationService(sheets, publisher, dry_run=False).run()

    assert publisher.calls == ["facebook_instagram", "gbp"]
    assert result["published"] == 1
    assert any("'Master View'!U4:U4" == update[0] for update in sheets.updates)


def test_partial_provider_failure_increments_retry_and_keeps_success() -> None:
    sheets = FakeSheets([["header"], master_row()])
    publisher = FakePublisher(fail_channel="gbp")
    result = SheetAutomationService(sheets, publisher, dry_run=False).run()

    assert result["failed"] == 1
    assert publisher.calls == ["facebook_instagram", "linkedin", "gbp"]
    assert any(update[0] == "'Master View'!AA4:AF4" and update[1][0][4] == 1 for update in sheets.updates)
