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
- Click **Import latest reports** to read the newest report for each pair and
  timeframe in every supported strategy/entry folder under MT5's Common Files
  directory. For example, AUDUSD M15 and GBPUSD M15 are imported separately.
  The market is read from report contents, including zero-trade reports; the
  newest export is selected by file modification time. Existing saved runs remain
  in the database, and exact duplicates are skipped.

The application reads existing reports. It does not run a backtest, place a
trade, or alter MT5 files. Original CSV/HTML bytes are copied into local storage.
HTML is parsed as text; uploaded source HTML is offered as a download, not run.
Exact duplicates are detected using source hashes and explicit import overrides.

The optional import fields support older reports and alternative entry techniques
such as cross-next-open. Missing settings stay unavailable instead of being
replaced with current strategy defaults. Current supported report families are
Out Down-Up, IN Up-Down, Gold LLP Up Sort, and 0 Break (called `0 Out` in MT5).

Command-line imports:

```powershell
.\.venv\Scripts\python.exe manage.py import_mt5 --latest
.\.venv\Scripts\python.exe manage.py import_mt5 --all
.\.venv\Scripts\python.exe manage.py import_mt5 'C:\path\report.csv'
```

Set `MT5_REPORTS_DIR` before starting the server to change the Common Files root.
The importer scans the supported strategy report folders, including cross-entry
variants and 0 Break Immediate.
The IN Up-Down cross-entry reports are read from `InUpDownCrossEntryBacktests`.

## Compare and export

- **Display names:** old Out Down reports are grouped under **Out Down-Up**.
  `EMA_TOUCH_NEXT_OPEN` is displayed as **5 candle entry**; the stored entry code
  and the recorded wait window stay attached to each run.
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

- **Point 0 label:** LLP, HHP, LLF, HLF, LHF or HHF is stored per trade. The main
  filter row selects these independently of OUT UP/DOWN and long/short direction.
  Metrics and both CSV exports use the same label-filtered trades.
  IN Up-Down reports explicitly mark point 0 as `IN`; this reported value is also
  preserved and available in the point 0 filter.
- Updated MT5 exports include `Point 0 label` and `Point 0 label candle`, frozen
  when point 3 completes the pattern. `UNRESOLVED` means no label was known then;
  this differs from `Not recorded`, which means the old report omitted the label.
- Legacy reports are enriched only when their saved setup explicitly records
  the label (for example `OUT 0 code: LLP`). Strategy names are not used to guess
  labels. Fill unrecorded historical labels by rerunning the updated MT5 script
  and importing its new reports. To recover explicit labels in stored reports:

  ```powershell
  .\.venv\Scripts\python.exe manage.py backfill_point_labels
  ```

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

The default local server is bound to **127.0.0.1** for use on this computer.
Local development remains accessible without a login. Hosted deployments require
an existing Django account to access results, imports, exports and report files.
There is no public registration. All authenticated accounts access this one
workspace; this is not a multi-customer application.

## Deploy on Render

`render.yaml` defines a Python web service, a Render Postgres database and a 1 GB
persistent disk for source CSV/HTML reports. Both services use Singapore. The
configuration uses paid compute plans; review Render's current charges before
deploying the Blueprint. Preparing or validating the file does not deploy it.

1. Push this repository to a private GitHub repository and connect that repository
   to your Render account. Keep `data/`, `.env` and local secrets out of Git.
2. Run `render login` and select your workspace. Optionally validate the Blueprint
   with `render blueprints validate render.yaml`.
3. In Render, choose **New > Blueprint**, connect the repository and select the
   branch containing `render.yaml`. Review the resources and charges, then deploy.
4. The build installs dependencies and collects static assets. The pre-deploy
   command applies database migrations. Gunicorn starts the application, and
   `/healthz/` checks database connectivity without exposing any report data.
5. Open the web service's **Shell** and run `python manage.py createsuperuser` to
   create your login interactively. Set your password in that shell, not in Git.
6. Open the service's HTTPS URL and sign in. Upload matching MT5 CSV/HTML files
   through **Import reports**.

Render supplies `DATABASE_URL` from the database, generates `DJANGO_SECRET_KEY`,
and sets the service hostname. Report files are stored under `/var/data/reports`
on the persistent disk. The build and pre-deploy steps do not require disk access;
the report directory is created at runtime. Files are downloaded through
authenticated Django views, not exposed as public media URLs. The persistent disk
limits this service to one instance and causes a brief interruption on redeploy.

The hosted server cannot scan the MT5 folders on your Windows computer. The local
**Import latest reports** option is hidden and disabled when hosted on Render.
Continue using it locally, or upload reports to the hosted workspace. No automatic
synchronization exists between the local and hosted databases.

### Transfer the existing local workspace

Transfer both the database records and the archived reports to retain original
run IDs, settings and source downloads. Do this once, into a fresh hosted journal,
before uploading any new reports there:

1. Stop the local server and back up the full `data/` directory.
2. Create `data/deployment/`, then export the journal only:

   ```powershell
   .\.venv\Scripts\python.exe manage.py dumpdata journal --indent 2 --output data/deployment/journal.json
   ```

3. Use Render's documented SCP/SFTP transfer to copy `journal.json` to
   `/var/data/journal.json` and copy the contents of local `data/reports/` to
   `/var/data/reports/`, preserving the UUID subdirectories and filenames.
4. In the Render service Shell, confirm the hosted journal has no runs yet, then
   run `python manage.py loaddata /var/data/journal.json`. This imports journal
   records only; the hosted login is created independently.
5. Compare run/trade counts and original report downloads before switching to the
   hosted workspace. Keep the local backup until the transfer is confirmed.

For a custom domain, add it in Render and set `DJANGO_ALLOWED_HOSTS` to its
hostname. If a separate trusted browser origin is needed, set
`DJANGO_CSRF_TRUSTED_ORIGINS` to comma-separated HTTPS origins. Production uses
secure cookies, HTTPS redirects, a fixed environment secret and required login.

## Development

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

Dependency: Django 5.2 LTS. Templates use ordinary HTML, CSS and small amounts of
vanilla JavaScript. No runtime requests to CDNs or analytics services are used.
