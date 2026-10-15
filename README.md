# Forex Backtest

A local Django + HTML application for keeping MT5 backtest results in SQLite,
comparing strategy versions and exporting filtered CSVs. No frontend build or
external service is required.

## Open the application

Double-click **start.cmd**, then open **http://127.0.0.1:8787**.
Keep its terminal open while using the app. Press Ctrl+C to stop it.

The first setup includes a Python environment and database. To recreate the
environment on another computer (Python 3.12+):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8787 --noreload
```

## Import reports

Open **Import reports** and either:

- Select a trade-level MT5 CSV and the HTML with the same filename.
- Click **Import latest reports** to read the newest report from each existing
  `ZeroOutBacktests`, `GoldLLPUpSortBacktests`, and `OutDownCandleBacktests` folder
  under MT5's Common Files directory.

The application reads existing reports. It does not run a backtest, place a
trade, or alter MT5 files. Original CSV/HTML bytes are copied into local storage.
HTML is parsed as text; uploaded source HTML is offered as a download, not run.
Exact duplicates are detected using source hashes and explicit import overrides.

The optional import fields support older reports and alternative entry techniques
such as cross-next-open. Missing settings stay unavailable instead of being
replaced with current strategy defaults. Current supported report families are
Out Down, Gold LLP Up Sort, and 0 Break (called `0 Out` in MT5).

Command-line imports:

```powershell
.\.venv\Scripts\python.exe manage.py import_mt5 --latest
.\.venv\Scripts\python.exe manage.py import_mt5 --all
.\.venv\Scripts\python.exe manage.py import_mt5 'C:\path\report.csv'
```

Set `MT5_REPORTS_DIR` before starting the server to change the Common Files root.
The importer only scans the three named report folders.

## Compare and export

- **Backtest runs:** filter by strategy/version, pair, timeframe, entry technique,
  wait window, pattern, long/short direction, cross direction, currency and exit dates.
- **Trade ledger:** the same filters apply to individual trades; open a trade to
  inspect all original fields, including its complete pattern description.
- **Run detail:** original settings, realised balance, monthly exit-date results,
  full trade ledger, warnings, source hashes and original downloads.
- **Strategies:** saved versions and pattern rules; exact runtime settings remain
  on each individual run.
- **Export CSV:** export the current selection as run summaries or individual
  trades. A run's export menu also includes its original files.

Dates in the filters are inclusive **exit dates**, applied to saved trades. They
do not change the original test window or rerun a strategy. Summary CSV exports
include `Metrics_Scope` and the applied trade filters. Return and full-run balance
drawdown are omitted for filtered subsets. The requested test end is exclusive;
the actual last candle is reported separately.

## Definitions and limits

- A win has net P/L > 0, a loss < 0, and break-even exactly 0, after commission.
  Win rate is wins / all closed trades, including break-even. Combined win rates
  use combined counts, never an average of percentages.
- Total gained sums positive net P/L. Total lost is the absolute sum of negative
  net P/L. Net profit is gained minus lost. Profit factor is gained / lost; it is
  infinite when there are profits and no losses, unavailable when both are zero.
- Statistics are calculated from imported trades, rather than independently
  editable summary values. MT5 CSV money values are rounded; small differences
  from original unrounded HTML totals are retained as import warnings.
- Balance is realised P/L ordered by exit candle. Same-candle exits are grouped
  before drawdown is measured, matching the source scripts' convention.
- Multiple runs are independent backtests. Overview totals sum their records;
  they are not a combined portfolio simulation. Different currencies are never
  added together. Monthly results group exits from one saved run, without reruns
  or resetting monthly capital.
- Broker candle timestamps are preserved without conversion. Source reports do
  not provide a broker timezone. `USE_TZ=False` deliberately avoids interpreting
  those times as Nepal time or UTC.
- This app does not change the backtest assumptions: the current scripts use
  candle ranges, recorded candle spreads, SL-first ties, zero swap/slippage,
  per-trade margin checks and realised balance. Floating equity and combined
  margin are not modeled. These are balance drawdowns, not equity drawdowns.
- Report sources are archived, but underlying candle/tick history is not included
  in existing reports. Archive that price dataset separately for full reproduction.
- Current cross direction is derived from the supported scripts' buy/upcross and
  sell/downcross convention when the entry technique is known. It is unavailable
  when that technique is not recorded.

## Data and backups

- SQLite database: `data/backtests.sqlite3`
- Preserved original reports: `data/reports/`
- Local Django secret: `data/.secret`

Stop the server, then copy the **entire data directory** to back up the database
and reports together. Data, reports, secrets and the virtual environment are
excluded from Git. Source code and migrations belong to the repository.

Runs and source reports are preserved; the interface intentionally has no bulk
delete action. Source hashes and a unique UUID identify every run. Importing a
different report or explicit settings variation creates a separate run.

The default server is bound to **127.0.0.1** for use on this computer. There is no
user login in this local version. Add authentication and production settings
before making it available over a network.

## Development

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

Dependency: Django 5.2 LTS. Templates use ordinary HTML, CSS and small amounts of
vanilla JavaScript. No runtime requests to CDNs or analytics services are used.
