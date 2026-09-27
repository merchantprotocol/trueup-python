# TrueUp for Python

The official client for the [TrueUp API](https://trueup-cloud.merchantprotocol.workers.dev/docs). Send TrueUp two ledgers (a supplier statement and your receiving log, your books and the bank feed, invoices and payments) and it pairs every row, then tells you what's only on one side, what was counted twice and where the numbers disagree.

Python 3.9+. One dependency (`httpx`).

## Install

```bash
pip install trueup
```

## Quickstart

Create an API key in the TrueUp dashboard (**API keys**), then:

```bash
export TRUEUP_API_KEY=tu_live_...
```

```python
from trueup import TrueUp

trueup = TrueUp()  # reads TRUEUP_API_KEY

result = trueup.reconcile("statement.csv", "receiving.csv")  # left: the side that bills or claims

print(result["headline"])
# 7 of 8 rows of statement.csv paired with receiving.csv; 1 only in statement.csv, ...
for f in result["findings"]:
    print(f["kind"], f["subject"], f["detail"], f["amount"])
# qty_mismatch statement.csv:row 5 Qty 24 vs qty_received 20; ... 99.6
# phantom statement.csv:row 6 no match on the other side 43.2
```

## Reconcile

A table is a path, file contents, or rows:

```python
from trueup import Table

trueup.reconcile("books.csv", "bank.csv")
trueup.reconcile(Table.content("books.csv", csv_text), Table.content("bank.csv", csv_bytes))
trueup.reconcile(
    Table.rows("invoices", [{"Invoice #": "INV-10101", "Date": "2026-06-09", "Total": "$2,999.31"}]),
    Table.rows("payments", [{"Received": "2026-07-01", "From": "ACME CONSTR", "Amount": "2999.31"}]),
)
```

CSV, TSV, JSON and JSON Lines are read, and date and number formats are detected. Nothing about the columns is configured.

Not sure which file is which? Send them all and TrueUp picks the pair and the sides:

```python
trueup.reconcile_files(["a.csv", "b.csv"])
```

**Reuse what was learned.** Every result carries `details["weights"]`. Pass them back to reconcile next month's files the same way, without learning again:

```python
march = trueup.reconcile("march-statement.csv", "march-receiving.csv")
april = trueup.reconcile("april-statement.csv", "april-receiving.csv", weights=march["details"]["weights"])
```

**Answer the questions.** Findings with `status == "unsure"` need a person. Send the decisions back:

```python
trueup.reconcile("statement.csv", "receiving.csv", answers={
    "same": [["statement.csv:row 12", "receiving.csv:row 11"]],
    "different": [["statement.csv:row 3", "receiving.csv:row 9"]],
})
```

Each call to `reconcile` or `reconcile_files` counts as one analysis on your plan.

## Findings

| `kind` | Meaning |
|---|---|
| `phantom` | Only on the left: billed or recorded, never matched |
| `unbilled` | Only on the right: received or paid, never billed |
| `duplicate`, `received_duplicate` | A copy of a row that's already paired |
| `qty_mismatch`, `price_change`, `amount_mismatch` | Paired rows whose numbers disagree |
| `unsure_pair` | A likely pair a person should confirm |

## Account and usage

```python
trueup.account()  # {"team": ..., "plan": ..., "key": ...}
trueup.usage()    # {"period": ..., "metrics": [{"metric": "analyses", "used": 2, "included": 50, ...}]}
trueup.plans()
```

## Errors

Every error is a `TrueUpError` with `status`, `code` (the API's error code) and `message`:

| Class | When |
|---|---|
| `AuthenticationError` | 401: missing, unknown or revoked key |
| `InvalidRequestError` | 400, 413, 415, 422: the request or the files need fixing (`unsupported_file`, `not_reconcilable`, ...) |
| `RateLimitError` | 429 `rate_limited`: retried automatically; `retry_after` seconds |
| `QuotaExceededError` | 429 `quota_exceeded`: the plan's monthly allowance is used up |
| `ServerError` | 5xx: retried automatically |
| `ConnectionError` | the API couldn't be reached |

```python
from trueup import QuotaExceededError

try:
    trueup.reconcile("a.csv", "b.csv")
except QuotaExceededError as e:
    print("Upgrade the plan:", e.message)
```

## Configuration

```python
TrueUp(
    api_key="tu_live_...",    # default: TRUEUP_API_KEY
    base_url="https://...",   # default: TRUEUP_BASE_URL, then the hosted API
    timeout=300,              # seconds per request
    max_retries=2,            # rate limits, 5xx and dropped connections
)
```

`TrueUp` is a context manager (`with TrueUp() as trueup:`) and closes its connection pool on exit.

## Development

The tests run in Docker against the live API:

```bash
export TRUEUP_API_KEY=tu_live_...   # a key for a test team (each run uses 2 analyses)
just test                            # or: docker compose run --rm test
```

## License

MIT
