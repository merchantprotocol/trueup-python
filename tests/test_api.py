"""Integration tests against the live TrueUp API. Need TRUEUP_API_KEY (and optionally TRUEUP_BASE_URL).

Each full run uses 2 analyses. Run in Docker: `just test` (or `docker compose run --rm test`).
"""

import csv
import os
from pathlib import Path

import pytest

from trueup import AuthenticationError, InvalidRequestError, Table, TrueUp

FIXTURES = Path(__file__).parent / "fixtures"
live = pytest.mark.skipif(not os.environ.get("TRUEUP_API_KEY"), reason="needs TRUEUP_API_KEY")


def rows(name):
    with open(FIXTURES / name, newline="") as fh:
        return list(csv.DictReader(fh))


def test_missing_api_key_fails_before_any_request(monkeypatch):
    monkeypatch.delenv("TRUEUP_API_KEY", raising=False)
    with pytest.raises(AuthenticationError) as e:
        TrueUp()
    assert e.value.code == "missing_api_key"


@live
def test_account_usage_plans():
    with TrueUp() as tu:
        account = tu.account()
        assert account["key"]["prefix"].startswith("tu_live_")
        assert any(m["metric"] == "analyses" for m in tu.usage()["metrics"])
        assert any(p["slug"] == "free" for p in tu.plans())


@live
def test_reconcile_files_then_rows_with_saved_weights():
    with TrueUp() as tu:
        result = tu.reconcile(FIXTURES / "statement.csv", FIXTURES / "receiving.csv")
        assert result["analysis"] == "reconcile"
        assert result["stats"]["paired"] == 7
        assert [(f["kind"], f["subject"]) for f in result["findings"]] == [
            ("qty_mismatch", "statement.csv:row 5"),
            ("phantom", "statement.csv:row 6"),
        ]
        assert result["findings"][1]["amount"] == 43.2
        weights = result["details"]["weights"]
        assert weights["format"] == "trueup.match-weights"

        again = tu.reconcile(Table.rows("statement.csv", rows("statement.csv")),
                             Table.rows("receiving.csv", rows("receiving.csv")), weights=weights)
        assert again["stats"]["paired"] == 7
        assert again["details"]["model"]["learned"] is False


@live
def test_errors_are_typed():
    with pytest.raises(AuthenticationError) as e:
        TrueUp(api_key="tu_live_" + "x" * 40).account()
    assert e.value.status == 401 and e.value.code == "invalid_api_key"
    with TrueUp() as tu, pytest.raises(InvalidRequestError) as e:
        tu.reconcile(FIXTURES / "statement.csv", Table.content("scan.pdf", b"%PDF-1.4"))
    assert e.value.status == 422 and e.value.code == "unsupported_file"
