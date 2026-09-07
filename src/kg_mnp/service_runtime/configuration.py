from __future__ import annotations

import os
from pathlib import Path

from kg_mnp.services.models import ServiceConfiguration


def load_configuration(workspace_root: Path | str = ".") -> ServiceConfiguration:
    root = Path(workspace_root).resolve()
    configuration = ServiceConfiguration(root.as_posix(), host=os.environ.get("KG_MNP_SERVICE_HOST", "127.0.0.1"), port=int(os.environ.get("KG_MNP_SERVICE_PORT", "8765")), tls_termination=os.environ.get("KG_MNP_TLS_TERMINATION", "false").lower() == "true", allowed_origins=tuple(filter(None, os.environ.get("KG_MNP_ALLOWED_ORIGINS", "").split(","))))
    configuration.validate()
    return configuration
