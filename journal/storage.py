import hashlib

from django.core.files.base import ContentFile
from django.core.files.storage import Storage

from .models import ReportFile


class DatabaseReportStorage(Storage):
    """Keep the same FileField names and original bytes across Render restarts."""

    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("Reports can only be opened for binary reading.")
        try:
            content = ReportFile.objects.values_list("content", flat=True).get(name=name)
        except ReportFile.DoesNotExist:
            raise FileNotFoundError(name) from None
        return ContentFile(bytes(content), name=name)

    def _save(self, name, content):
        data = b"".join(content.chunks())
        ReportFile.objects.create(
            name=name, content=data, byte_count=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        return name

    def exists(self, name):
        return ReportFile.objects.filter(name=name).exists()

    def size(self, name):
        try:
            return ReportFile.objects.values_list("byte_count", flat=True).get(name=name)
        except ReportFile.DoesNotExist:
            raise FileNotFoundError(name) from None

    def delete(self, name):
        ReportFile.objects.filter(name=name).delete()

    def url(self, name):
        raise NotImplementedError("Use the authenticated source-report download view.")
