from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

import jwt

from app.integrations.base import IntegrationError


GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_API_ROOT = "https://sheets.googleapis.com/v4/spreadsheets"


@dataclass(frozen=True)
class GoogleSheetsConfig:
    spreadsheet_id: str
    service_account_json: str
    master_range: str = "'Master View'!A3:AI97"
    log_range: str = "'Automation Log'!A1:L500"
    token_uri: str = "https://oauth2.googleapis.com/token"


class GoogleSheetsClient:
    """Small, dependency-light Google Sheets API client for server-side jobs.

    The service-account JSON is read only from runtime secrets. It is never
    returned by the API or written to the workbook.
    """

    def __init__(self, config: GoogleSheetsConfig) -> None:
        self.config = config
        try:
            credentials = json.loads(config.service_account_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise IntegrationError("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
        if not credentials.get("client_email") or not credentials.get("private_key"):
            raise IntegrationError("Google service-account JSON is missing client_email or private_key.")
        self._credentials = credentials
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _access_token(self) -> str:
        now = int(time.time())
        if self._token and now < self._token_expires_at - 60:
            return self._token
        payload = {
            "iss": self._credentials["client_email"],
            "scope": GOOGLE_SHEETS_SCOPE,
            "aud": self._credentials.get("token_uri") or self.config.token_uri,
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(payload, self._credentials["private_key"], algorithm="RS256")
        body = urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}).encode("utf-8")
        request = Request(payload["aud"], data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed Google token endpoint from operator config
                token_response = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise IntegrationError("Google Sheets authentication failed.") from exc
        token = token_response.get("access_token")
        if not token:
            raise IntegrationError("Google Sheets authentication returned no access token.")
        self._token = str(token)
        self._token_expires_at = time.time() + int(token_response.get("expires_in", 3600))
        return self._token

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - URL is built from the configured spreadsheet ID
                body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise IntegrationError(f"Google Sheets request failed: {method} {url.rsplit('/', 1)[-1][:80]}") from exc
        try:
            return json.loads(body) if body else {}
        except ValueError as exc:
            raise IntegrationError("Google Sheets returned an invalid response.") from exc

    def read_values(self, range_name: str) -> list[list[Any]]:
        encoded_range = quote(range_name, safe="")
        result = self._request("GET", f"{SHEETS_API_ROOT}/{self.config.spreadsheet_id}/values/{encoded_range}")
        return result.get("values") or []

    def update_values(self, range_name: str, values: list[list[Any]]) -> None:
        self._request(
            "POST",
            f"{SHEETS_API_ROOT}/{self.config.spreadsheet_id}/values:batchUpdate",
            {"valueInputOption": "USER_ENTERED", "data": [{"range": range_name, "majorDimension": "ROWS", "values": values}]},
        )

    def append_values(self, range_name: str, values: list[Any]) -> None:
        encoded_range = quote(range_name, safe="")
        query = urlencode({"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"})
        self._request(
            "POST",
            f"{SHEETS_API_ROOT}/{self.config.spreadsheet_id}/values/{encoded_range}:append?{query}",
            {"majorDimension": "ROWS", "values": [values]},
        )

    def health_check(self) -> bool:
        try:
            self._request("GET", f"{SHEETS_API_ROOT}/{self.config.spreadsheet_id}?fields=spreadsheetId")
            return True
        except IntegrationError:
            return False
