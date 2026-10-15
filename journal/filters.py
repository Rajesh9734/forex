from django import forms
from django.db.models import Q
from .models import BacktestRun, ENTRY_TECHNIQUES, PATTERNS, POINT0_LABELS, Trade


class FilterForm(forms.Form):
    strategy = forms.ChoiceField(required=False, label="Strategy")
    version = forms.ChoiceField(required=False, label="Version")
    symbol = forms.ChoiceField(required=False, label="Pair / symbol")
    timeframe = forms.ChoiceField(required=False, label="Timeframe")
    entry = forms.ChoiceField(required=False, label="Entry technique", choices=[("", "All entry techniques")] + ENTRY_TECHNIQUES)
    pattern = forms.ChoiceField(required=False, label="Pattern", choices=[("", "All patterns")] + PATTERNS)
    point0_label = forms.ChoiceField(required=False, label="Point 0 label", choices=[("", "All labels")] + POINT0_LABELS + [("NOT_RECORDED", "Not recorded")])
    direction = forms.ChoiceField(required=False, label="Trade direction", choices=[("", "All directions"), ("LONG", "Long trades"), ("SHORT", "Short trades"), ("BOTH", "Runs with both sides enabled")])
    cross = forms.ChoiceField(required=False, label="Cross direction", choices=[("", "All crosses"), ("UPCROSS", "Upcross"), ("DOWNCROSS", "Downcross"), ("BOTH", "Runs using both crosses")])
    wait = forms.IntegerField(required=False, min_value=1, max_value=10000, label="Max wait candles")
    from_date = forms.DateField(required=False, label="Exit date from", widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(required=False, label="Exit date through", widget=forms.DateInput(attrs={"type": "date"}))
    outcome = forms.ChoiceField(required=False, label="Outcome", choices=[("", "All outcomes"), ("won", "Won"), ("lost", "Lost"), ("flat", "Break even")])
    currency = forms.ChoiceField(required=False, label="Currency")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field, lookup in [("strategy", "strategy__name"), ("version", "strategy__version"), ("symbol", "symbol"), ("timeframe", "timeframe"), ("currency", "currency")]:
            values = BacktestRun.objects.order_by(lookup).values_list(lookup, flat=True).distinct()
            self.fields[field].choices = [("", f"All {self.fields[field].label.lower()}s")] + [(v, v) for v in values]

    def clean(self):
        data = super().clean()
        if data.get("from_date") and data.get("to_date") and data["from_date"] > data["to_date"]:
            self.add_error("to_date", "Choose a date on or after the start.")
        return data


def selection(params, run_id=None):
    form = FilterForm(params)
    runs = BacktestRun.objects.select_related("strategy")
    if run_id:
        runs = runs.filter(pk=run_id)
    if not form.is_valid():
        return form, runs.none(), Trade.objects.none(), False
    data = form.cleaned_data
    for field, lookup in [("strategy", "strategy__name"), ("version", "strategy__version"), ("symbol", "symbol"), ("timeframe", "timeframe"), ("entry", "entry_technique"), ("wait", "max_wait_candles"), ("currency", "currency")]:
        if data.get(field):
            runs = runs.filter(**{lookup: data[field]})
    if data.get("direction") == "BOTH":
        runs = runs.filter(trade_direction="BOTH")
    if data.get("cross") == "BOTH":
        runs = runs.filter(cross_direction="BOTH")
    trades = Trade.objects.filter(run__in=runs).select_related("run__strategy")
    if data.get("direction") in ("LONG", "SHORT"):
        trades = trades.filter(side="BUY" if data["direction"] == "LONG" else "SELL")
    if data.get("cross") in ("UPCROSS", "DOWNCROSS"):
        side = "BUY" if data["cross"] == "UPCROSS" else "SELL"
        trades = trades.filter(Q(run__cross_direction=data["cross"]) | Q(run__cross_direction="BOTH", side=side))
    if data.get("pattern"):
        trades = trades.filter(pattern=data["pattern"])
    if data.get("point0_label"):
        trades = trades.filter(point0_label="" if data["point0_label"] == "NOT_RECORDED" else data["point0_label"])
    if data.get("from_date"):
        trades = trades.filter(exit_at__date__gte=data["from_date"])
    if data.get("to_date"):
        trades = trades.filter(exit_at__date__lte=data["to_date"])
    if data.get("outcome"):
        lookup = {"won": "net_profit__gt", "lost": "net_profit__lt", "flat": "net_profit"}[data["outcome"]]
        trades = trades.filter(**{lookup: 0})
    scoped = any(data.get(k) for k in ("pattern", "point0_label", "from_date", "to_date", "outcome")) or data.get("direction") in ("LONG", "SHORT") or data.get("cross") in ("UPCROSS", "DOWNCROSS")
    if scoped:
        runs = runs.filter(pk__in=trades.values("run_id"))
    return form, runs, trades, scoped
