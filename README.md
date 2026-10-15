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
trade, or alter MT5 files. Original CSV/HTML bytes are archived with each run.
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
The seven corresponding `TS...Backtests` folders are also scanned. TS strategies
remain separate from their originals. Import the main trades CSV and its matching
HTML; the `_exits.csv` companion is not an individual-trades input.

TS reports use `Weighted exit` for the combined exit price. Their matching HTML
contains each actual half-exit, including price, candle, lots, percent, reason and
P/L. These validated records are stored with the trade's JSON source data, so no
database schema migration is required. The original HTML remains archived.
Trade IDs and exit IDs are shown in the ledger, trade details and exports. Older
reports that lack explicit IDs keep their original numeric trade reference.

The run export menu includes **Individual exits CSV**. Win rates count each
original trade once. Balance and monthly profit realise each part on its exit
candle; monthly trade counts use the original position's final-close month.
Per-part and combined CSV amounts are rounded independently. Any cent difference
is allocated to the final cash flow for totals, preserving the reported values
in the individual-exit table. CSV-only TS imports explicitly flag missing exit
parts and cannot export guessed individual exits.

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

On the hosted Supabase deployment, PostgreSQL also contains the original report
bytes. Back up that database to retain both records and sources; copying Render's
temporary filesystem is not a hosted-data backup.

Runs and source reports are preserved; the interface intentionally has no bulk
delete action. Source hashes and a unique UUID identify every run. Importing a
different report or explicit settings variation creates a separate run.

The default local server is bound to **127.0.0.1** for use on this computer.
Local development remains accessible without a login. Hosted deployments require
an existing Django account to access results, imports, exports and report files.
There is no public registration. All authenticated accounts access this one
workspace; this is not a multi-customer application.

## Deploy: free Render web app + Supabase PostgreSQL

`render.yaml` defines one free Render web service in Singapore. It creates no
Render database or persistent disk. Supabase stores the journal and original
CSV/HTML bytes, so a Render restart does not erase them. Both services remain
subject to their providers' free-tier limits; Render may sleep when inactive.

1. Create a Supabase project. Under **Connect**, select **Session pooler** on
   port **5432** and copy its PostgreSQL connection URL. Replace the password
   placeholder and percent-encode reserved password characters. Use the exact
   host and username supplied by Supabase.
2. Push this repository to a private GitHub repository and connect that repository
   to Render. Keep `data/`, `.env` and local secrets out of Git.
3. In Render, choose **New > Blueprint**, select the repository and the branch
   containing `render.yaml`, and review the free web service before deploying.
4. Supply the prompted environment values in Render:
   - `DATABASE_URL`: Supabase's Session pooler PostgreSQL URL.
   - `DJANGO_SUPERUSER_USERNAME`: the initial website login username.
   - `DJANGO_SUPERUSER_EMAIL`: your login email.
   - `DJANGO_SUPERUSER_PASSWORD`: a strong initial login password.
5. Render generates `DJANGO_SECRET_KEY`. The build installs dependencies and
   collects static files. At startup, the app prepares its private schema, applies
   migrations and creates the initial owner only if one does not already exist.
   These startup steps also work on the free plan, which has no pre-deploy command
   or interactive service Shell. Existing passwords are not reset on redeploy.
6. Open the service's HTTPS URL and sign in. Upload matching MT5 CSV/HTML files
   through **Import reports**.

The `forex_backtest` PostgreSQL schema keeps Django's tables separate from
Supabase's public Data API schema. Do not add it to Supabase's exposed schemas.
The app uses an encrypted PostgreSQL connection. Report bytes stay in a separate
`ReportFile` table and are fetched only for source downloads, rather than loaded
with every dashboard query. Their original names and SHA-256 hashes are retained.
Files are downloaded through authenticated views, not public media URLs.

The hosted server cannot scan the MT5 folders on your Windows computer. The local
**Import latest reports** option is hidden and disabled when hosted. Continue
using it locally, or upload reports to the hosted workspace. The local SQLite
journal and hosted Supabase journal are independent; no automatic sync exists.

### Transfer the existing local workspace

The transfer preserves original run IDs, settings, trades and report downloads.
Use a fresh Supabase application schema and transfer before importing new reports
online. Existing Supabase platform tables in other schemas are not changed.

1. Stop the local server and back up the complete `data/` directory.
2. Apply migrations, copy report bytes into the journal and export it:

   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate
   .\.venv\Scripts\python.exe manage.py archive_report_files
   .\.venv\Scripts\python.exe manage.py dumpdata journal --indent 2 --output data/deployment/journal.json
   ```

   Create `data/deployment/` first. This JSON is private data, excluded from Git.
   The archive command checks source hashes and preserves filesystem originals.
3. Run the transfer tool locally. It prompts for the Supabase Session pooler URL
   without displaying it, prepares the schema and imports the private fixture:

   ```powershell
   .\.venv\Scripts\python.exe tools/transfer_to_postgres.py data/deployment/journal.json
   ```

   It refuses to import into a journal that already has runs, strategies, trades
   or archived report files. It never exports the local login or local secret.
4. Confirm the hosted run/trade counts and original downloads before switching.
   Keep the local backup until the transfer is confirmed. New local records are
   not automatically copied after this one-time transfer.

For a custom domain, add it in Render and set `DJANGO_ALLOWED_HOSTS` to its
hostname. If needed, set `DJANGO_CSRF_TRUSTED_ORIGINS` to comma-separated HTTPS
origins. Production uses secure cookies, HTTPS redirects, an environment secret
and required login. Database-backed file storage is enabled by
`DJANGO_REPORT_STORAGE=database`; local development still uses filesystem reports.

## Development

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

Dependency: Django 5.2 LTS. Templates use ordinary HTML, CSS and small amounts of
vanilla JavaScript. No runtime requests to CDNs or analytics services are used.
