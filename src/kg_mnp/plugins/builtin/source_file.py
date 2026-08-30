"""Local regular-file source adapter."""

from pathlib import Path

from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import SourceReadRequest, SourceReadResult


class LocalFileSource:
    def read(self, request: SourceReadRequest) -> SourceReadResult:
        path = Path(request.source_path)
        if path.is_symlink() or not path.is_file():
            raise PluginError("source must be a non-symlink regular file")
        stat = path.stat()
        if stat.st_size > request.limits.max_source_bytes:
            raise PluginError("SOURCE_SIZE_LIMIT_EXCEEDED")
        return SourceReadResult(content=path.read_bytes(), display_name=path.name)
