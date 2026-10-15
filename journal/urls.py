from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("trades/", views.trade_list, name="trades"),
    path("trades/<int:pk>/", views.trade_detail, name="trade_detail"),
    path("strategies/", views.strategies, name="strategies"),
    path("import/", views.import_page, name="import"),
    path("import/latest/", views.import_latest, name="import_latest"),
    path("runs/<uuid:pk>/", views.run_detail, name="run_detail"),
    path("runs/<uuid:pk>/source/<str:kind>/", views.source_download, name="source_download"),
    path("export/summary.csv", views.export_summary, name="export_summary"),
    path("export/trades.csv", views.export_trades, name="export_trades"),
]
