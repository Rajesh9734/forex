from django.conf import settings


def workspace(request):
    return {
        "hosted_workspace": settings.IS_RENDER,
        "local_report_import_enabled": settings.LOCAL_REPORT_IMPORT_ENABLED,
    }
