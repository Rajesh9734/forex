from collections import defaultdict
from decimal import Decimal
from itertools import groupby

ZERO = Decimal("0")


def summarize(trades, initial_balance=None):
    rows = list(trades)
    won = [t.net_profit for t in rows if t.net_profit > 0]
    lost = [-t.net_profit for t in rows if t.net_profit < 0]
    gained, losses = sum(won, ZERO), sum(lost, ZERO)
    net = gained - losses
    # Count outcomes once per original trade, while realising each TS part
    # on its own exit candle. Group same-candle cash flows for balance drawdown.
    balance = initial_balance if initial_balance is not None else ZERO
    peak, drawdown, drawdown_pct = balance, ZERO, ZERO
    curve = [(None, balance)]
    cash_flows = sorted((flow for trade in rows for flow in trade.cash_flows), key=lambda flow: flow[0])
    for exit_at, group in groupby(cash_flows, key=lambda flow: flow[0]):
        balance += sum((amount for _, amount in group), ZERO)
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
        if initial_balance is not None and peak > 0:
            drawdown_pct = max(drawdown_pct, (peak - balance) / peak * 100)
        curve.append((exit_at, balance))
    return {
        "total": len(rows), "wins": len(won), "losses": len(lost),
        "breakeven": len(rows) - len(won) - len(lost),
        "point0_labels": sorted({t.point0_label or "NOT_RECORDED" for t in rows}),
        "labelled_trades": sum(bool(t.point0_label) for t in rows),
        "missing_labels": sum(not t.point0_label for t in rows),
        "longs": sum(t.side == "BUY" for t in rows), "shorts": sum(t.side == "SELL" for t in rows),
        "win_rate": Decimal(len(won)) * 100 / len(rows) if rows else ZERO,
        "gained": gained, "lost": losses, "net": net,
        "profit_factor": gained / losses if losses else None,
        "profit_factor_label": f"{gained / losses:.2f}" if losses else ("∞" if gained else "—"),
        "return_pct": net / initial_balance * 100 if initial_balance else None,
        "final_balance": initial_balance + net if initial_balance is not None else None,
        "drawdown": drawdown, "drawdown_pct": drawdown_pct if initial_balance is not None else None,
        "curve": curve,
    }


def monthly_results(trades):
    groups = defaultdict(list)
    cash = defaultdict(lambda: ZERO)
    for trade in trades:
        groups[trade.exit_at.strftime("%Y-%m")].append(trade)
        for exit_at, amount in trade.cash_flows:
            cash[exit_at.strftime("%Y-%m")] += amount
    results = []
    for month in sorted(set(groups) | set(cash)):
        closed = groups[month]
        wins = sum(trade.net_profit > 0 for trade in closed)
        results.append({"month": month, "net": cash[month], "total": len(closed),
                        "win_rate": Decimal(wins) * 100 / len(closed) if closed else ZERO})
    return results


def chart_points(curve, width=1000, height=240):
    if len(curve) < 2:
        return "", []
    values = [float(value) for _, value in curve]
    lo, hi = min(values), max(values)
    span = hi - lo or max(abs(hi) * .01, 1)
    points = " ".join(f"{20 + i / (len(values) - 1) * (width - 40):.1f},{height - 24 - (value - lo) / span * (height - 48):.1f}" for i, value in enumerate(values))
    return points, [hi, (hi + lo) / 2, lo]
