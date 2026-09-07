from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from kg_mnp.services.models import ServiceConfiguration


def load_configuration(workspace_root: Path | str = ".") -> ServiceConfiguration:
    root = Path(workspace_root).resolve()
    configuration = ServiceConfiguration(root.as_posix(), host=os.environ.get("KG_MNP_SERVICE_HOST", "127.0.0.1"), port=int(os.environ.get("KG_MNP_SERVICE_PORT", "8765")), tls_termination=os.environ.get("KG_MNP_TLS_TERMINATION", "false").lower() == "true", allowed_origins=tuple(filter(None, os.environ.get("KG_MNP_ALLOWED_ORIGINS", "").split(","))), domain_packs_root=os.environ.get("KG_MNP_DOMAIN_PACKS_ROOT"))
    configuration = replace(configuration, reasoner_jar=os.environ.get("KG_MNP_REASONER_JAR"),
                            workbench_root=os.environ.get("KG_MNP_WORKBENCH_ROOT"),
                            review_profile=os.environ.get("KG_MNP_REVIEW_PROFILE", "PRODUCTION_MULTI_ROLE"),
                            allow_insecure_loopback_session=os.environ.get("KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION", "false").lower() == "true")
    configuration.validate()
    return configuration
