from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from zhigou_toolchain.environment import get_setting
from zhigou_toolchain.services.models import ServiceConfiguration


def load_configuration(workspace_root: Path | str = ".") -> ServiceConfiguration:
    root = Path(workspace_root).resolve()
    configuration = ServiceConfiguration(root.as_posix(), host=get_setting("SERVICE_HOST", "127.0.0.1"), port=int(get_setting("SERVICE_PORT", "8765")), tls_termination=get_setting("TLS_TERMINATION", "false").lower() == "true", allowed_origins=tuple(filter(None, get_setting("ALLOWED_ORIGINS", "").split(","))), domain_packs_root=get_setting("DOMAIN_PACKS_ROOT"))
    configuration = replace(configuration, reasoner_jar=get_setting("REASONER_JAR"),
                            workbench_root=get_setting("WORKBENCH_ROOT"),
                            review_profile=get_setting("REVIEW_PROFILE", "PRODUCTION_MULTI_ROLE"),
                            allow_insecure_loopback_session=get_setting("ALLOW_INSECURE_LOOPBACK_SESSION", "false").lower() == "true")
    configuration.validate()
    return configuration
