"""TrueUp API client.

    from trueup import TrueUp

    trueup = TrueUp()                                    # reads TRUEUP_API_KEY
    result = trueup.reconcile("statement.csv", "receiving.csv")
    for f in result["findings"]:
        print(f["kind"], f["subject"], f["detail"])
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import httpx

__version__ = "0.1.0"
__all__ = [
    "TrueUp", "Table", "TrueUpError", "AuthenticationError", "InvalidRequestError", "NotFoundError",
    "RateLimitError", "QuotaExceededError", "ServerError", "ConnectionError", "DEFAULT_BASE_URL",
]

DEFAULT_BASE_URL = "https://trueup-cloud.merchantprotocol.workers.dev"

Row = Mapping[str, Union[str, int, float, bool, None]]


class TrueUpError(Exception):
    """Any error the API returned, or a failure to reach it. ``code`` is the API's error code; branch on it."""

    def __init__(self, message: str, status: int = 0, code: str = "connection_error", body: Any = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.body = body


class AuthenticationError(TrueUpError):
    """401: missing, unknown or revoked API key."""


class InvalidRequestError(TrueUpError):
    """400, 413, 415, 422: the request or the files need fixing."""


class NotFoundError(TrueUpError):
    """404, 405."""


class RateLimitError(TrueUpError):
    """429 rate_limited: slow down. ``retry_after`` is in seconds."""

    retry_after: Optional[float] = None


class QuotaExceededError(TrueUpError):
    """429 quota_exceeded: the team used its plan's allowance this month. Retrying won't help."""


class ServerError(TrueUpError):
    """5xx."""


class ConnectionError(TrueUpError):  # noqa: A001  (shadows the builtin inside this module only)
    """The API couldn't be reached, or took too long."""


def _error_for(status: int, code: str, message: str, body: Any, retry_after: Optional[str]) -> TrueUpError:
    if status == 401:
        return AuthenticationError(message, status, code, body)
    if status == 429 and code == "quota_exceeded":
        return QuotaExceededError(message, status, code, body)
    if status == 429:
        e = RateLimitError(message, status, code, body)
        e.retry_after = float(retry_after) if retry_after else None
        return e
    if status in (404, 405):
        return NotFoundError(message, status, code, body)
    if status >= 500:
        return ServerError(message, status, code, body)
    return InvalidRequestError(message, status, code, body)


class Table:
    """A table to reconcile, from a file, file contents, or rows. ``name`` is how findings refer to its rows
    ("statement.csv:row 5").

        Table.file("statement.csv")
        Table.content("statement.csv", csv_text)
        Table.rows("statement.csv", [{"Date": "2026-08-03", "Amount": "$99.60"}, ...])
    """

    def __init__(self, name: str, content: Optional[bytes] = None, rows: Optional[Sequence[Row]] = None):
        self.name = name
        self._content = content
        self._rows = list(rows) if rows is not None else None

    @classmethod
    def file(cls, path: Union[str, os.PathLike], name: Optional[str] = None) -> "Table":
        p = Path(path)
        return cls(name or p.name, content=p.read_bytes())

    @classmethod
    def content(cls, name: str, content: Union[str, bytes]) -> "Table":
        return cls(name, content=content.encode() if isinstance(content, str) else content)

    @classmethod
    def rows(cls, name: str, rows: Sequence[Row]) -> "Table":
        return cls(name, rows=rows)

    @property
    def is_rows(self) -> bool:
        return self._rows is not None

    def _file(self) -> Tuple[str, bytes]:
        if self._rows is not None:
            stem = self.name.rsplit(".", 1)[0] if "." in self.name else self.name
            return stem + ".json", json.dumps(self._rows).encode()
        return self.name, self._content or b""


TableLike = Union[Table, str, os.PathLike]


def _table(t: TableLike) -> Table:
    return t if isinstance(t, Table) else Table.file(t)


class TrueUp:
    """A client for the TrueUp API.

    Args:
        api_key:     defaults to the TRUEUP_API_KEY environment variable
        base_url:    defaults to TRUEUP_BASE_URL, then the hosted API
        timeout:     seconds per request (default 300: big ledgers take a while)
        max_retries: retries for rate limits, server errors and dropped connections (default 2)
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 300.0,
                 max_retries: int = 2, http_client: Optional[httpx.Client] = None):
        key = api_key or os.environ.get("TRUEUP_API_KEY") or None
        if not key:
            raise AuthenticationError("No API key: pass api_key= or set TRUEUP_API_KEY. Create one in the TrueUp "
                                      "dashboard under API keys.", 0, "missing_api_key")
        self._api_key = key
        self.base_url = (base_url or os.environ.get("TRUEUP_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.max_retries = max_retries
        self._http = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "TrueUp":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------ endpoints

    def account(self) -> Dict[str, Any]:
        """The team, plan and key behind this client's API key."""
        return self._request("GET", "/v1/account")

    def usage(self) -> Dict[str, Any]:
        """This month's usage for the key's team."""
        return self._request("GET", "/v1/usage")

    def plans(self) -> List[Dict[str, Any]]:
        """The plans a team can be on."""
        return self._request("GET", "/v1/plans")["plans"]

    def reconcile(self, left: TableLike, right: TableLike, *, weights: Optional[Mapping[str, Any]] = None,
                  answers: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Reconcile two tables. ``left`` is the side that bills or claims (a statement, your books), ``right`` the
        other side (receiving log, bank feed). A path, or a :class:`Table`. Counts as one analysis.

        ``weights``: ``details["weights"]`` from an earlier result, to apply instead of learning again.
        ``answers``: ``{"same": [[left row, right row]], "different": [...]}``, decisions a person made.
        """
        lt, rt = _table(left), _table(right)
        if lt.is_rows and rt.is_rows:
            body = {"left": {"name": lt.name, "rows": lt._rows}, "right": {"name": rt.name, "rows": rt._rows}}
            if weights is not None:
                body["weights"] = weights
            if answers is not None:
                body["answers"] = answers
            return self._request("POST", "/v1/reconcile", json_body=body)
        files = [("left", lt._file()), ("right", rt._file())]
        return self._request("POST", "/v1/reconcile", files=files, data=_options(weights, answers))

    def reconcile_files(self, files: Sequence[TableLike], *, weights: Optional[Mapping[str, Any]] = None,
                        answers: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Send two or more files; TrueUp picks the pair to reconcile and which side is which. One analysis."""
        parts = [("files", _table(f)._file()) for f in files]
        return self._request("POST", "/v1/reconcile", files=parts, data=_options(weights, answers))

    # ------------------------------------------------------------ transport

    def _request(self, method: str, path: str, json_body: Any = None, files: Any = None, data: Any = None) -> Any:
        headers = {"authorization": f"Bearer {self._api_key}", "accept": "application/json",
                   "user-agent": f"trueup-python/{__version__}"}
        attempt = 0
        while True:
            try:
                res = self._http.request(method, self.base_url + path, headers=headers, json=json_body, files=files,
                                         data=data)
            except httpx.HTTPError as e:
                if attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    attempt += 1
                    continue
                raise ConnectionError(f"Couldn't reach TrueUp at {self.base_url}: {e}") from e
            try:
                payload = res.json() if res.content else None
            except ValueError:
                payload = res.text
            if res.is_success:
                return payload
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            error = _error_for(res.status_code, err.get("code") or f"http_{res.status_code}",
                               err.get("message") or f"HTTP {res.status_code}", payload, res.headers.get("retry-after"))
            if isinstance(error, (RateLimitError, ServerError)) and attempt < self.max_retries:
                wait = error.retry_after if isinstance(error, RateLimitError) and error.retry_after else _backoff(attempt)
                time.sleep(wait)
                attempt += 1
                continue
            raise error


def _options(weights: Optional[Mapping[str, Any]], answers: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    out = {}
    if weights is not None:
        out["weights"] = json.dumps(weights)
    if answers is not None:
        out["answers"] = json.dumps(answers)
    return out


def _backoff(attempt: int) -> float:
    return min(30.0, 2.0 ** attempt) * (0.5 + random.random() / 2)
