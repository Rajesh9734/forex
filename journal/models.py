import uuid
from django.db import models

ENTRY_TECHNIQUES = [
    ("EMA_TOUCH_NEXT_OPEN", "5 candle entry"),
    ("CROSS_NEXT_OPEN", "EMA cross → next open"),
    ("EMA_TOUCH_CLOSE", "EMA touch → candle close"),
    ("CROSS_CLOSE", "EMA cross → candle close"),
    ("UNKNOWN", "Not recorded"),
]
PATTERNS = [(x, x.replace("_", " ")) for x in ("OUT_UP", "OUT_DOWN", "IN_UP", "IN_DOWN")]
POINT0_LABELS = [(x, x) for x in ("LLP", "HHP", "LLF", "HLF", "LHF", "HHF")] + [("UNRESOLVED", "Unresolved at pattern confirmation")]
DIRECTIONS = [("LONG", "Long"), ("SHORT", "Short"), ("BOTH", "Both"), ("UNKNOWN", "Not recorded")]


class StrategyVersion(models.Model):
    name = models.CharField(max_length=160)
    version = models.CharField(max_length=40, default="Not recorded")
    rules = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "version"]
        constraints = [models.UniqueConstraint(fields=["name", "version"], name="strategy_version_unique")]

    def __str__(self):
        return f"{self.name} · v{self.version}"


def report_upload_path(instance, filename):
    return f"{instance.id}/{filename}"


class BacktestRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    strategy = models.ForeignKey(StrategyVersion, on_delete=models.PROTECT, related_name="runs")
    fingerprint = models.CharField(max_length=64, unique=True)
    symbol = models.CharField(max_length=40, db_index=True)
    timeframe = models.CharField(max_length=16, db_index=True)
    currency = models.CharField(max_length=12)
    requested_start = models.DateTimeField(null=True, blank=True)
    requested_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    entry_technique = models.CharField(max_length=40, choices=ENTRY_TECHNIQUES, default="UNKNOWN", db_index=True)
    max_wait_candles = models.PositiveIntegerField(null=True, blank=True)
    cross_direction = models.CharField(max_length=16, default="UNKNOWN")
    trade_direction = models.CharField(max_length=10, choices=DIRECTIONS, default="UNKNOWN")
    pattern_types = models.JSONField(default=list)
    initial_balance = models.DecimalField(max_digits=26, decimal_places=8, null=True, blank=True)
    risk_percent = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    reward_risk = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    commission_per_lot = models.DecimalField(max_digits=26, decimal_places=8, null=True, blank=True)
    break_even_enabled = models.BooleanField(null=True)
    settings = models.JSONField(default=dict)
    import_warnings = models.JSONField(default=list)
    source_name = models.CharField(max_length=255)
    source_reference = models.TextField(blank=True)
    csv_sha256 = models.CharField(max_length=64)
    html_sha256 = models.CharField(max_length=64, blank=True)
    csv_report = models.FileField(upload_to=report_upload_path)
    html_report = models.FileField(upload_to=report_upload_path, blank=True)
    time_basis = models.CharField(max_length=160, default="MT5 candle times, as reported; broker timezone not supplied")
    notes = models.TextField(blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-imported_at"]

    @property
    def short_id(self):
        return str(self.id)[:8]

    @property
    def pattern_label(self):
        return " + ".join(p.replace("_", " ") for p in self.pattern_types) or "Not recorded"


class Trade(models.Model):
    run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="trades")
    number = models.PositiveIntegerField()
    side = models.CharField(max_length=5, choices=[("BUY", "Long"), ("SELL", "Short")], db_index=True)
    pattern = models.CharField(max_length=16, blank=True, db_index=True)
    point0_label = models.CharField(max_length=16, choices=POINT0_LABELS, blank=True, default="", db_index=True)
    point0_label_at = models.DateTimeField(null=True, blank=True)
    point0_label_source = models.CharField(max_length=24, blank=True, default="")
    signal_at = models.DateTimeField(null=True, blank=True)
    touch_at = models.DateTimeField(null=True, blank=True)
    entry_at = models.DateTimeField(db_index=True)
    exit_at = models.DateTimeField(db_index=True)
    entry_price = models.DecimalField(max_digits=30, decimal_places=12)
    exit_price = models.DecimalField(max_digits=30, decimal_places=12)
    initial_sl = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    final_sl = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    tp = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    lots = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    gross_profit = models.DecimalField(max_digits=26, decimal_places=8, null=True, blank=True)
    commission = models.DecimalField(max_digits=26, decimal_places=8, null=True, blank=True)
    net_profit = models.DecimalField(max_digits=26, decimal_places=8)
    reported_balance = models.DecimalField(max_digits=26, decimal_places=8, null=True, blank=True)
    exit_reason = models.CharField(max_length=120, blank=True)
    sl_moved = models.BooleanField(default=False)
    both_touched = models.BooleanField(default=False)
    raw = models.JSONField(default=dict)

    class Meta:
        ordering = ["entry_at", "number"]
        constraints = [models.UniqueConstraint(fields=["run", "number"], name="run_trade_number_unique")]

    @property
    def outcome(self):
        return "Won" if self.net_profit > 0 else "Lost" if self.net_profit < 0 else "Break even"
