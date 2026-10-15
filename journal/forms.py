from decimal import Decimal
from django import forms
from .models import CURRENT_ENTRY_TECHNIQUES


class ImportForm(forms.Form):
    csv_file = forms.FileField(label="Trade report CSV", widget=forms.ClearableFileInput(attrs={"accept": ".csv"}))
    html_file = forms.FileField(label="Matching HTML report", required=False, widget=forms.ClearableFileInput(attrs={"accept": ".html,.htm"}), help_text="Recommended. Captures version, test dates, starting balance and rules.")
    strategy_name = forms.CharField(max_length=160, required=False, label="Strategy name", help_text="Leave blank to read it from the report.")
    strategy_version = forms.CharField(max_length=40, required=False, label="Version")
    entry_technique = forms.ChoiceField(required=False, choices=[("", "Read from report")] + CURRENT_ENTRY_TECHNIQUES)
    cross_direction = forms.ChoiceField(required=False, label="Cross direction", choices=[("", "Read from report"), ("UPCROSS", "Upcross"), ("DOWNCROSS", "Downcross"), ("BOTH", "Both"), ("UNKNOWN", "Not recorded")])
    max_wait_candles = forms.IntegerField(required=False, min_value=1, max_value=10000, label="Maximum wait candles")
    initial_balance = forms.DecimalField(required=False, min_value=Decimal("0.01"), max_digits=24, decimal_places=2, label="Starting balance")
    requested_start = forms.DateTimeField(required=False, label="Test start", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), input_formats=["%Y-%m-%dT%H:%M"])
    requested_end = forms.DateTimeField(required=False, label="Test end (exclusive)", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), input_formats=["%Y-%m-%dT%H:%M"])
    notes = forms.CharField(required=False, max_length=5000, widget=forms.Textarea(attrs={"rows": 3}), label="Notes")

    def clean(self):
        data = super().clean()
        for field in ("csv_file", "html_file"):
            uploaded = data.get(field)
            if uploaded and uploaded.size > 20 * 1024 * 1024:
                self.add_error(field, "Each report must be smaller than 20 MB.")
        if data.get("requested_start") and data.get("requested_end") and data["requested_start"] >= data["requested_end"]:
            self.add_error("requested_end", "End must be after the start.")
        return data
