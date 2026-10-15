"""Import MT5 trade reports without executing scripts or changing source files."""
import csv
import hashlib
import io
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

from .models import BacktestRun, POINT0_LABELS, StrategyVersion, Trade

MAX_REPORT_BYTES = 20 * 1024 * 1024
REPORT_FOLDERS = ("ZeroOutBacktests", "GoldLLPUpSortBacktests", "OutDownCandleBacktests",
                  "ZeroOutCrossEntryBacktests", "GoldLLPCrossEntryBacktests", "OutDownCrossEntryBacktests",
                  "ZeroBreakImmediateBacktests", "InUpDownCrossEntryBacktests")


class ImportProblem(ValueError):
    pass


class ReportHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metadata, self.heading, self.text = {}, "", []
        self.row, self.cell, self.in_heading = [], None, False
        self.heading_parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self.in_heading = True
        if tag == "tr":
            self.row = []
        if tag in ("th", "td"):
            self.cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self.in_heading:
            self.heading_parts.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_heading = False
            self.heading = " ".join("".join(self.heading_parts).split())
        if tag in ("th", "td") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and len(self.row) == 2:
            self.metadata[self.row[0]] = self.row[1]


def decode_report(content):
    if len(content) > MAX_REPORT_BYTES:
        raise ImportProblem("Each report must be smaller than 20 MB.")
    encodings = ("utf-16",) if content.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "cp1252")
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeError:
            continue
    raise ImportProblem("The report encoding could not be read. Export UTF-8 from MT5.")


def number(value, label, required=False):
    if value is None or str(value).strip() == "":
        if required:
            raise ImportProblem(f"Missing {label}.")
        return None
    try:
        parsed = Decimal(str(value).strip().replace(",", ""))
        if not parsed.is_finite() or abs(parsed) >= Decimal("1e17"):
            raise InvalidOperation
        return parsed
    except InvalidOperation:
        raise ImportProblem(f"Invalid {label}: {str(value)[:70]}") from None


def report_number(value):
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value or "")
    return number(match.group(), "report number") if match else None


def timestamp(value, label, required=False):
    value = (value or "").strip()
    if not value:
        if required:
            raise ImportProblem(f"Missing {label}.")
        return None
    for fmt in ("%Y.%m.%d %H:%M", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ImportProblem(f"Invalid {label}: {value[:60]}. Expected an MT5 candle timestamp.")


def window(value):
    dates = re.findall(r"\d{4}[.-]\d{2}[.-]\d{2} \d{2}:\d{2}(?::\d{2})?", value or "")
    return tuple(timestamp(value, "window date") for value in dates[:2]) if len(dates) >= 2 else (None, None)


def pattern_types(value):
    return sorted({f"{kind.upper()}_{direction.upper()}" for kind, direction in re.findall(r"\b(OUT|IN)[ _-]+(UP|DOWN)\b", value or "", re.I)})


def point0_details(row):
    """Read an explicitly exported label. Never derive it from a strategy name."""
    allowed = {code for code, _ in POINT0_LABELS}
    label = (row.get("Point 0 label") or row.get("OUT 0 code") or "").strip().upper()
    source = "CSV_COLUMN" if label else ""
    setup = " | ".join(value for key, value in row.items() if re.match(r"^(?:OUT|IN) 0(?: LLP)? / ", key))
    matches = set(re.findall(r"\bOUT\s+0\s+(?:code|label)\s*:\s*(LLP|HHP|LLF|HLF|LHF|HHF|UNRESOLVED)\b", setup, re.I))
    matches.update(re.findall(r"\bOUT\s+0\s+(LLP|HHP|LLF|HLF|LHF|HHF)\s*:", setup, re.I))
    matches.update(re.findall(r"\bIN\s+0\s+state\s*:\s*(IN)\b", setup, re.I))
    matches = {code.upper() for code in matches}
    if len(matches) > 1 or (label and matches and matches != {label}):
        raise ImportProblem("Conflicting point 0 labels in the CSV.")
    if not label and matches:
        label, source = matches.pop(), "LEGACY_SETUP"
    if label and label not in allowed:
        raise ImportProblem(f"Unknown point 0 label: {label}.")
    label_time = row.get("Point 0 label candle", "")
    if not label_time:
        match = re.search(r"\b(?:OUT\s+0\s+label candle|IN\s+0\s+state captured):\s*(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", setup, re.I)
        label_time = match.group(1) if match else ""
    return label, timestamp(label_time, "point 0 label candle") if label_time else None, source


def infer_strategy(heading, rows, source_name):
    candidate = " ".join([heading, source_name] + [row.get("Strategy", "") for row in rows[:10]])
    if re.search(r"0\s*break\s*immediate|zerobreakimmediate", candidate, re.I):
        return "0 Break Immediate"
    if re.search(r"\bin[ _-]+(?:up|down)\b|inupdown", candidate, re.I):
        return "IN Up-Down"
    if re.search(r"\bout[ _-]+down[-/]up\b", heading, re.I):
        return "Out Down-Up"
    if re.search(r"gold|llp", candidate, re.I):
        return "Gold LLP Up Sort"
    if re.search(r"\b0\s*(?:out|break)\b|zeroout", candidate, re.I):
        return "0 Break"
    if re.search(r"out[ _-]*down|out[ _-]*up", candidate, re.I):
        return "Out Down-Up"
    return heading or "Imported strategy"


def canonical_strategy_name(name):
    value = name.strip()
    if re.fullmatch(r"out\s+down(?:[-/]up)?", value, re.I):
        return "Out Down-Up"
    if re.fullmatch(r"in\s+(?:up[-/]down|down[-/]up)", value, re.I):
        return "IN Up-Down"
    return value


def read_payload(csv_bytes, csv_name, html_bytes=b"", html_name="", overrides=None):
    overrides = {key: value for key, value in (overrides or {}).items() if value not in (None, "")}
    if html_bytes and Path(csv_name).stem != Path(html_name).stem:
        raise ImportProblem("Choose the HTML report with the same filename as the CSV.")
    report = ReportHTML()
    if html_bytes:
        html_text = decode_report(html_bytes)
        if not html_text.rstrip().lower().endswith("</html>"):
            raise ImportProblem("The HTML report appears incomplete. Wait for MT5 to finish saving it.")
        report.feed(html_text)
    settings = report.metadata
    text = decode_report(csv_bytes)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
    required = {"Trade", "Symbol", "Timeframe", "Side", "Entry candle", "Exit candle", "Entry", "Exit", "Net P/L", "Currency"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ImportProblem("This must be an individual-trades CSV. Missing columns: " + ", ".join(sorted(missing)))
    try:
        rows = [{key: value or "" for key, value in row.items() if key is not None} for row in reader if any(row.values())]
    except csv.Error as exc:
        raise ImportProblem(f"Could not parse CSV: {exc}") from exc
    symbols, timeframes, currencies = ({r[field].strip() for r in rows} for field in ("Symbol", "Timeframe", "Currency"))
    if any(len(values) > 1 for values in (symbols, timeframes, currencies)):
        raise ImportProblem("One report must contain exactly one pair, timeframe and currency.")
    heading_text = " ".join(report.text)
    context = re.search(r"Candle backtest\s*[-–]\s*(\S+)\s+(M\d+|H\d+|D1|W1|MN1)\b", heading_text)
    symbol = next(iter(symbols), "") or (context.group(1) if context else "")
    timeframe = next(iter(timeframes), "") or (context.group(2) if context else "")
    currency = next(iter(currencies), "")
    if not currency:
        match = re.search(r"\b([A-Z]{3})\b", settings.get("Initial balance", ""))
        currency = match.group(1) if match else ""
    if not all((symbol, timeframe, currency)):
        raise ImportProblem("A zero-trade CSV needs its matching HTML report to identify pair, timeframe and currency.")
    if context and (symbol, timeframe) != context.groups():
        raise ImportProblem("The HTML pair/timeframe does not match this CSV.")
    strategy_name = canonical_strategy_name(overrides.get("strategy_name") or infer_strategy(report.heading, rows, csv_name))
    version = overrides.get("strategy_version") or settings.get("Calculator version", "Not recorded")
    warnings = []
    entry_rule = settings.get("Entry rule", "")
    lower_rule = entry_rule.lower()
    technique = "UNKNOWN"
    next_open = bool(re.search(r"next(?:\s+available)?\s+candle(?:'s)?\s+open", lower_rule))
    if "touch" in lower_rule and next_open:
        technique = "EMA_TOUCH_NEXT_OPEN"
    elif next_open:
        technique = "CROSS_NEXT_OPEN"
    elif "touch" in lower_rule and "close" in lower_rule:
        technique = "EMA_TOUCH_CLOSE"
    elif "cross" in lower_rule and "close" in lower_rule:
        technique = "CROSS_CLOSE"
    technique = overrides.get("entry_technique") or technique
    wait_match = re.search(r"candles?\s+1\s*[-–]\s*(\d+)", entry_rule, re.I)
    wait_candles = overrides.get("max_wait_candles")
    if wait_candles is None and wait_match:
        wait_candles = int(wait_match.group(1))
    if technique in {"CROSS_NEXT_OPEN", "CROSS_CLOSE"}:
        wait_candles = None
    requested_start, requested_end = window(settings.get("Requested window (end exclusive)", ""))
    actual_start, actual_end = window(settings.get("Actual candles used for trading", ""))
    if overrides.get("requested_start"):
        requested_start = timestamp(overrides["requested_start"], "requested start")
    if overrides.get("requested_end"):
        requested_end = timestamp(overrides["requested_end"], "requested end")
    if requested_start and requested_end and requested_start >= requested_end:
        raise ImportProblem("The requested end must be after the start.")
    initial_balance = overrides.get("initial_balance")
    if initial_balance is None:
        initial_balance = report_number(settings.get("Initial balance", ""))
    initial_balance = number(initial_balance, "starting balance")
    if initial_balance is not None and initial_balance <= 0:
        raise ImportProblem("Starting balance must be positive.")
    combined_settings = settings.get("EMA / basis / risk / reward / leverage", "")
    risk_match = re.search(r"([\d.]+)%", combined_settings)
    reward_match = re.search(r"([\d.]+)R\b", combined_settings)
    observed_sides = {r["Side"].strip().upper() for r in rows}
    direction_text = settings.get("Trade directions", "")
    declared_sides = set()
    if re.search(r"\bbuys?\b", direction_text, re.I):
        declared_sides.add("BUY")
    if re.search(r"\bsells?\b", direction_text, re.I):
        declared_sides.add("SELL")
    enabled_sides = declared_sides or observed_sides
    direction = "BOTH" if enabled_sides == {"BUY", "SELL"} else "LONG" if enabled_sides == {"BUY"} else "SHORT" if enabled_sides == {"SELL"} else "UNKNOWN"
    patterns = pattern_types(direction_text) or sorted({p for row in rows for p in pattern_types(row.get("Strategy", ""))})
    trades, seen = [], set()
    decimal_columns = {
        "entry_price": ("Entry", True), "exit_price": ("Exit", True), "initial_sl": ("SL", False),
        "final_sl": ("Final SL", False), "tp": ("TP", False), "lots": ("Lots", False),
        "gross_profit": ("Gross P/L", False), "commission": ("Commission", False),
        "net_profit": ("Net P/L", True), "reported_balance": ("Balance after exit", False),
    }
    for row_index, row in enumerate(rows, 2):
        try:
            trade_number = int(row["Trade"])
            if trade_number < 1 or trade_number in seen:
                raise ImportProblem("Duplicate or invalid trade number.")
            seen.add(trade_number)
            side = row["Side"].strip().upper()
            if side not in {"BUY", "SELL"}:
                raise ImportProblem("Side must be BUY or SELL.")
            entry_at = timestamp(row["Entry candle"], "entry date", True)
            exit_at = timestamp(row["Exit candle"], "exit date", True)
            if exit_at < entry_at:
                raise ImportProblem("Exit date is before entry date.")
            pattern = pattern_types(row.get("Strategy", ""))
            point0_label, point0_label_at, point0_label_source = point0_details(row)
            if point0_label_at and point0_label_at > entry_at:
                raise ImportProblem("Point 0 label candle is after entry; it cannot describe a label known before this trade.")
            trade = Trade(number=trade_number, side=side, pattern=pattern[0] if len(pattern) == 1 else "",
                          point0_label=point0_label, point0_label_at=point0_label_at,
                          point0_label_source=point0_label_source,
                          entry_at=entry_at, exit_at=exit_at,
                          signal_at=timestamp(row.get("Signal candle"), "signal date"),
                          touch_at=timestamp(row.get("Touch candle"), "touch date"),
                          exit_reason=row.get("Exit reason", ""),
                          sl_moved=row.get("SL moved to entry", "").lower() == "true",
                          both_touched=row.get("Both touched SL wins", "").lower() == "true", raw=row)
            for field, (column, required_value) in decimal_columns.items():
                setattr(trade, field, number(row.get(column), column, required_value))
            trades.append(trade)
        except (ImportProblem, ValueError) as exc:
            raise ImportProblem(f"CSV row {row_index}: {exc}") from exc
    if not html_bytes:
        warnings.append("CSV only: version, original test window and execution settings may be unavailable. Attach the matching HTML to preserve them.")
    if technique == "UNKNOWN":
        warnings.append("Entry technique was not recorded. Choose it explicitly when importing.")
    if initial_balance is None:
        warnings.append("Starting balance is unavailable. Return and balance drawdown percentages cannot be calculated.")
    if not requested_start or not requested_end:
        warnings.append("Original requested window is unavailable. Trade dates do not establish the tested data coverage.")
    missing_labels = sum(not trade.point0_label for trade in trades)
    if missing_labels:
        warnings.append(f"Point 0 label was not recorded for {missing_labels} trades. Rerun the updated MT5 script and import its new reports to fill those labels.")
    expected_net = report_number(settings.get("Net profit", ""))
    calculated_net = sum((trade.net_profit for trade in trades), Decimal("0"))
    tolerance = Decimal("0.02") + Decimal("0.005") * len(trades)
    if expected_net is not None and abs(expected_net - calculated_net) > tolerance:
        raise ImportProblem("The HTML net profit does not reconcile with the CSV. Choose the matching reports.")
    elif expected_net is not None and expected_net != calculated_net:
        warnings.append("Per-trade CSV values are rounded. Recalculated totals can differ slightly from the unrounded HTML totals.")
    counts = next((value for key, value in settings.items() if key.startswith("Trades /")), "")
    expected_count = report_number(counts)
    if expected_count is not None and expected_count != len(trades):
        raise ImportProblem("The HTML trade count does not match the CSV.")
    digest = hashlib.sha256(csv_bytes + b"\0" + html_bytes + b"\0" + json.dumps(overrides, sort_keys=True, default=str).encode()).hexdigest()
    rules = {k: v for k, v in settings.items() if k in {"Pattern rule", "First-break rule", "After 0 breaks", "OUT 0 filter", "Candle event priority", "Position policy"}}
    run_fields = dict(
        fingerprint=digest, symbol=symbol, timeframe=timeframe, currency=currency,
        requested_start=requested_start, requested_end=requested_end, actual_start=actual_start, actual_end=actual_end,
        entry_technique=technique, max_wait_candles=wait_candles,
        trade_direction=direction, pattern_types=patterns,
        cross_direction=overrides.get("cross_direction") or (("BOTH" if direction == "BOTH" else "UPCROSS" if direction == "LONG" else "DOWNCROSS" if direction == "SHORT" else "UNKNOWN") if technique != "UNKNOWN" else "UNKNOWN"),
        initial_balance=initial_balance,
        risk_percent=number(risk_match.group(1), "risk percentage") if risk_match else None,
        reward_risk=number(reward_match.group(1), "reward risk") if reward_match else None,
        commission_per_lot=report_number(settings.get("Commission per lot, both sides", "")),
        break_even_enabled=settings.get("Move SL to entry at 1R", "").startswith("Enabled") if "Move SL to entry at 1R" in settings else None,
        settings={**settings, "Import overrides": {k: str(v) for k, v in overrides.items()}},
        import_warnings=warnings, source_name=Path(csv_name).name,
        csv_sha256=hashlib.sha256(csv_bytes).hexdigest(), html_sha256=hashlib.sha256(html_bytes).hexdigest() if html_bytes else "",
        notes=overrides.get("notes", ""),
    )
    return strategy_name, version, rules, run_fields, trades


def import_reports(csv_bytes, csv_name, html_bytes=b"", html_name="", overrides=None, source_reference=""):
    name, version, rules, fields, trades = read_payload(csv_bytes, csv_name, html_bytes, html_name, overrides)
    existing = BacktestRun.objects.filter(fingerprint=fields["fingerprint"]).first()
    if existing:
        return existing, False
    saved_files = []
    try:
        with transaction.atomic():
            strategy, _ = StrategyVersion.objects.get_or_create(name=name, version=version, defaults={"rules": rules})
            run = BacktestRun(strategy=strategy, source_reference=source_reference, **fields)
            run.csv_report.save(Path(csv_name).name, ContentFile(csv_bytes), save=False)
            saved_files.append(run.csv_report)
            if html_bytes:
                run.html_report.save(Path(html_name).name, ContentFile(html_bytes), save=False)
                saved_files.append(run.html_report)
            run.save()
            for trade in trades:
                trade.run = run
            Trade.objects.bulk_create(trades, batch_size=400)
            return run, True
    except Exception as exc:
        for field in saved_files:
            field.storage.delete(field.name)
        if isinstance(exc, IntegrityError):
            existing = BacktestRun.objects.filter(fingerprint=fields["fingerprint"]).first()
            if existing:
                return existing, False
        raise


def _report_market(csv_path):
    """Read the market from report contents, including zero-trade exports."""
    try:
        text = decode_report(csv_path.read_bytes())
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
        row = next((row for row in reader if any(row.values())), {})
        symbol = (row.get("Symbol") or "").strip()
        timeframe = (row.get("Timeframe") or "").strip()
        if symbol and timeframe:
            return symbol, timeframe

        report = ReportHTML()
        report.feed(decode_report(csv_path.with_suffix(".html").read_bytes()))
        context = re.search(r"Candle backtest\s*[-–]\s*(\S+)\s+(M\d+|H\d+|D1|W1|MN1)\b", " ".join(report.text))
        if context:
            return context.groups()
    except (ImportProblem, OSError, csv.Error):
        # Leave unreadable reports in the import queue so their errors are shown.
        pass
    return None


def discover_reports(root, latest=False):
    paths = []
    for folder in REPORT_FOLDERS:
        directory = Path(root) / folder
        if directory.is_dir():
            found = sorted((p for p in directory.glob("*.csv") if p.with_suffix(".html").is_file()), key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)
            if not latest:
                paths.extend(found)
                continue
            seen_markets = set()
            for path in found:
                market = _report_market(path)
                if market is None:
                    paths.append(path)
                elif market not in seen_markets:
                    # Each folder identifies a strategy and its entry variant.
                    seen_markets.add(market)
                    paths.append(path)
    return paths
