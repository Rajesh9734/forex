import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.paginator import Paginator
from django.db import DatabaseError, connection
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .filters import selection
from .forms import ImportForm
from .importer import ImportProblem, discover_reports, import_reports
from .metrics import chart_points, monthly_results, summarize
from .models import BacktestRun, StrategyVersion, Trade


@login_not_required
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("Unavailable", status=503, content_type="text/plain")
    return HttpResponse("OK", content_type="text/plain")


def grouped_selection(request, run_id=None):
    form, runs, trades, scoped = selection(request.GET, run_id)
    grouped = defaultdict(list)
    all_trades = list(trades)
    for trade in all_trades:
        grouped[trade.run_id].append(trade)
    run_rows = []
    for run in runs:
        run.stats = summarize(grouped[run.id], None if scoped else run.initial_balance)
        run_rows.append(run)
    return form, run_rows, all_trades, scoped


def dashboard(request):
    form, rows, trades, scoped = grouped_selection(request)
    by_currency = defaultdict(list)
    for trade in trades:
        by_currency[trade.run.currency].append(trade)
    currencies = [{"currency": currency, **summarize(values)} for currency, values in sorted(by_currency.items())]
    stats = summarize(trades)
    ordering = request.GET.get("sort", "recent")
    if ordering == "win_rate":
        rows.sort(key=lambda r: (r.stats["win_rate"], r.stats["total"]), reverse=True)
    elif ordering == "trades":
        rows.sort(key=lambda r: r.stats["total"], reverse=True)
    elif ordering == "net":
        rows.sort(key=lambda r: (r.currency, -r.stats["net"]))
    page = Paginator(rows, 20).get_page(request.GET.get("page"))
    return render(request, "journal/dashboard.html", {
        "section": "runs", "filter_form": form, "page_obj": page,
        "run_count": len(rows), "stats": stats, "currencies": currencies,
        "single_currency": currencies[0] if len(currencies) == 1 else None,
        "scoped": scoped, "sort": ordering, "total_saved": BacktestRun.objects.count(),
    })


def trade_list(request):
    form, runs, trades, scoped = selection(request.GET)
    page = Paginator(trades.order_by("-exit_at", "-number"), 50).get_page(request.GET.get("page"))
    return render(request, "journal/trades.html", {"section": "trades", "filter_form": form, "page_obj": page, "scoped": scoped})


def run_detail(request, pk):
    run = get_object_or_404(BacktestRun.objects.select_related("strategy"), pk=pk)
    form, _, trades, scoped = grouped_selection(request, run.id)
    stats = summarize(trades, None if scoped else run.initial_balance)
    points, ticks = chart_points(stats["curve"])
    monthly = monthly_results(trades)
    highest = max([abs(row["net"]) for row in monthly] or [Decimal("1")]) or Decimal("1")
    for row in monthly:
        row["width"] = abs(row["net"]) / highest * 100
    page = Paginator(sorted(trades, key=lambda t: (t.exit_at, t.number), reverse=True), 40).get_page(request.GET.get("page"))
    return render(request, "journal/run_detail.html", {
        "section": "runs", "run": run, "stats": stats, "filter_form": form, "scoped": scoped,
        "chart_points": points, "chart_ticks": ticks, "monthly": monthly, "page_obj": page,
    })


def strategies(request):
    versions = StrategyVersion.objects.annotate(run_count=Count("runs"))
    return render(request, "journal/strategies.html", {"section": "strategies", "versions": versions})


def trade_detail(request, pk):
    trade = get_object_or_404(Trade.objects.select_related("run__strategy"), pk=pk)
    return render(request, "journal/trade_detail.html", {"section": "trades", "trade": trade, "run": trade.run})


def import_page(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        csv_file, html_file = values.pop("csv_file"), values.pop("html_file", None)
        for key in ("requested_start", "requested_end"):
            if values.get(key):
                values[key] = values[key].strftime("%Y-%m-%d %H:%M")
        try:
            run, created = import_reports(csv_file.read(), csv_file.name,
                                         html_file.read() if html_file else b"",
                                         html_file.name if html_file else "", values)
            messages.success(request, "Report imported." if created else "This exact report and settings are already saved. Opened the existing run.")
            return redirect("run_detail", pk=run.id)
        except ImportProblem as exc:
            form.add_error(None, str(exc))
    detected_count = len(discover_reports(settings.MT5_REPORTS_DIR, latest=True)) if settings.LOCAL_REPORT_IMPORT_ENABLED else 0
    return render(request, "journal/import.html", {"section": "import", "form": form, "detected_count": detected_count})


@require_POST
def import_latest(request):
    if not settings.LOCAL_REPORT_IMPORT_ENABLED:
        raise Http404("Local MT5 report folders are available only on your computer.")
    created, existing, errors = 0, 0, []
    for csv_path in discover_reports(settings.MT5_REPORTS_DIR, latest=True):
        html_path = csv_path.with_suffix(".html")
        try:
            _, is_new = import_reports(csv_path.read_bytes(), csv_path.name,
                                      html_path.read_bytes() if html_path.exists() else b"", html_path.name,
                                      source_reference=str(csv_path))
            created += is_new
            existing += not is_new
        except (ImportProblem, OSError) as exc:
            errors.append(f"{csv_path.name}: {exc}")
    if created or existing:
        messages.success(request, f"{created} new runs imported. {existing} existing reports skipped.")
    if not created and not existing and not errors:
        messages.info(request, "No reports found in the configured MT5 report folders.")
    for error in errors:
        messages.error(request, error)
    return redirect("dashboard")


def csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        safe = []
        for value in row:
            if value is None:
                value = ""
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            if isinstance(value, Decimal):
                value = format(value, "f")
            safe.append(value)
        writer.writerow(safe)
    return response


def date_string(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def export_summary(request):
    form, runs, trades, scoped = grouped_selection(request, request.GET.get("run") or None)
    if not form.is_valid():
        return HttpResponse("Correct the filters before exporting.", status=400)
    headers = ["Run_ID", "Strategy", "Strategy_Version", "Pair", "Timeframe", "From_Date", "To_Date_Exclusive", "Actual_First_Candle", "Actual_Last_Candle", "Entry_Technique", "Max_Wait_Candles", "Cross_Direction", "Pattern_Type", "Trade_Direction", "Initial_Balance", "Risk_Percent", "Currency", "Total_Trades", "Long_Trades", "Short_Trades", "Wins", "Losses", "Break_Even", "Win_Rate_Percent", "Total_Gained", "Total_Lost", "Net_Profit", "Return_Percent", "Profit_Factor", "Max_Balance_Drawdown", "Max_Balance_Drawdown_Percent", "Metrics_Scope", "Filter_Exit_From", "Filter_Exit_Through", "Filter_Pattern", "Filter_Direction", "Filter_Cross", "Filter_Outcome", "Source_CSV_SHA256"]
    output = []
    for run in runs:
        s = run.stats
        output.append([
            str(run.id), run.strategy.name, run.strategy.version, run.symbol, run.timeframe,
            date_string(run.requested_start), date_string(run.requested_end), date_string(run.actual_start), date_string(run.actual_end),
            run.entry_technique, run.max_wait_candles, run.cross_direction, "+".join(run.pattern_types), run.trade_direction,
            run.initial_balance, run.risk_percent, run.currency, s["total"], s["longs"], s["shorts"], s["wins"], s["losses"], s["breakeven"],
            s["win_rate"].quantize(Decimal(".01")), s["gained"], s["lost"], s["net"],
            s["return_pct"].quantize(Decimal(".01")) if s["return_pct"] is not None else None,
            s["profit_factor"].quantize(Decimal(".0001")) if s["profit_factor"] is not None else ("Infinite" if s["gained"] else ""),
            s["drawdown"] if not scoped else None, s["drawdown_pct"].quantize(Decimal(".01")) if s["drawdown_pct"] is not None else None,
            "FILTERED_TRADES" if scoped else "FULL_RUN", request.GET.get("from_date", ""), request.GET.get("to_date", ""),
            request.GET.get("pattern", ""), request.GET.get("direction", ""), request.GET.get("cross", ""), request.GET.get("outcome", ""), run.csv_sha256,
            "+".join(s["point0_labels"]), request.GET.get("point0_label", ""), s["labelled_trades"], s["missing_labels"],
        ])
    headers += ["Point_0_Labels", "Filter_Point_0_Label", "Trades_With_Point_0_Label", "Trades_Missing_Point_0_Label"]
    return csv_response("backtest-summary.csv", headers, output)


def export_trades(request):
    form, runs, trades, scoped = selection(request.GET, request.GET.get("run") or None)
    if not form.is_valid():
        return HttpResponse("Correct the filters before exporting.", status=400)
    headers = ["Run_ID", "Strategy", "Strategy_Version", "Pair", "Timeframe", "Entry_Technique", "Max_Wait_Candles", "Pattern_Type", "Trade", "Side", "Signal_Candle", "Touch_Candle", "Entry_Candle", "Exit_Candle", "Entry", "Exit", "Init_SL", "Fin_SL", "TP", "Lots", "Gross_PL", "Commission", "Net_PL", "Currency", "Outcome", "Exit_Reason", "SL_Moved", "Both_Touched_SL_Wins"]
    rows = ([str(t.run_id), t.run.strategy.name, t.run.strategy.version, t.run.symbol, t.run.timeframe, t.run.entry_technique,
             t.run.max_wait_candles, t.pattern, t.number, t.side, date_string(t.signal_at), date_string(t.touch_at), date_string(t.entry_at), date_string(t.exit_at),
             t.entry_price, t.exit_price, t.initial_sl, t.final_sl, t.tp, t.lots, t.gross_profit, t.commission, t.net_profit,
             t.run.currency, t.outcome, t.exit_reason, t.sl_moved, t.both_touched,
             t.point0_label or "NOT_RECORDED", date_string(t.point0_label_at), t.point0_label_source,
             t.display_id, t.weighted_exit, json.dumps(t.raw.get("_partial_exits", []), ensure_ascii=False)] for t in trades.iterator())
    headers += ["Point_0_Label", "Point_0_Label_Candle", "Point_0_Label_Source", "Trade_ID", "Weighted_Exit", "Exit_Parts"]
    return csv_response("backtest-trades.csv", headers, rows)


def export_exits(request):
    form, _, trades, _ = selection(request.GET, request.GET.get("run") or None)
    if not form.is_valid():
        return HttpResponse("Correct the filters before exporting.", status=400)
    trades = list(trades)
    if any(trade.weighted_exit and not trade.exit_parts for trade in trades):
        return HttpResponse("Individual exits are unavailable for a selected TS run. Import its matching HTML report first.", status=400)
    headers = ["Run_ID", "Strategy", "Strategy_Version", "Pair", "Timeframe", "Trade_ID", "Exit_ID", "Side",
               "Exit_Candle", "Exit_Price", "Closed_Lots", "Closed_Percent", "Reason", "Gross_PL", "Commission", "Net_PL", "Currency"]

    def rows():
        for trade in trades:
            context = [str(trade.run_id), trade.run.strategy.name, trade.run.strategy.version,
                       trade.run.symbol, trade.run.timeframe, trade.display_id]
            if trade.exit_parts:
                for part in trade.exit_parts:
                    yield context + [part.exit_id, trade.side, date_string(part.exit_at), part.exit_price,
                                     part.lots, part.percent, part.reason, part.gross_profit,
                                     part.commission, part.net_profit, trade.run.currency]
            else:
                yield context + [f"{trade.display_id}-X1", trade.side, date_string(trade.exit_at), trade.exit_price,
                                 trade.lots, 100, trade.exit_reason, trade.gross_profit, trade.commission,
                                 trade.net_profit, trade.run.currency]
    return csv_response("backtest-exits.csv", headers, rows())


def source_download(request, pk, kind):
    run = get_object_or_404(BacktestRun, pk=pk)
    field = run.csv_report if kind == "csv" else run.html_report if kind == "html" else None
    if not field or not field.storage.exists(field.name):
        raise Http404("Source report is unavailable.")
    return FileResponse(field.open("rb"), as_attachment=True, filename=Path(field.name).name)
