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
    # Imported reports round per-trade money to cents. Group same-candle exits
    # before calculating balance drawdown, matching the source scripts.
    balance = initial_balance if initial_balance is not None else ZERO
    peak, drawdown, drawdown_pct = balance, ZERO, ZERO
    curve = [(None, balance)]
    for exit_at, group in groupby(sorted(rows, key=lambda t: (t.exit_at, t.number)), key=lambda t: t.exit_at):
        balance += sum((t.net_profit for t in group), ZERO)
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
        if initial_balance is not None and peak > 0:
            drawdown_pct = max(drawdown_pct, (peak - balance) / peak * 100)
        curve.append((exit_at, balance))
    return {
        "total": len(rows), "wins": len(won), "losses": len(lost),
        "breakeven": len(rows) - len(won) - len(lost),
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
    for trade in trades:
        groups[trade.exit_at.strftime("%Y-%m")].append(trade)
    return [{"month": month, **summarize(rows)} for month, rows in sorted(groups.items())]


def chart_points(curve, width=1000, height=240):
    if len(curve) < 2:
        return "", []
    values = [float(value) for _, value in curve]
    lo, hi = min(values), max(values)
    span = hi - lo or max(abs(hi) * .01, 1)
    points = " ".join(f"{20 + i / (len(values) - 1) * (width - 40):.1f},{height - 24 - (value - lo) / span * (height - 48):.1f}" for i, value in enumerate(values))
    return points, [hi, (hi + lo) / 2, lo]
