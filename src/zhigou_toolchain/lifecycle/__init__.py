"""Offline immutable ontology registry and controlled release lifecycle."""
__version__ = "0.7.0"
from .changes import (
    attach_candidate_package,
    create_change_proposal,
    evaluate_change,
    submit_change_proposal,
)
from .consumer import register_consumer
from .contracts import build, validate, verify
from .diff import check_version, create_diff
from .environment import (
    activate,
    execute_activation,
    init_environment,
    propose_activation,
    review_activation,
    rollback,
)
from .errors import LifecycleError
from .feedback import add_feedback, inspect_feedback
from .registry.manifest import init_registry
from .regression import plan_regression, run_regression
from .release import (
    attest_release,
    create_release_candidate,
    publish_release,
    record_review,
)

__all__ = ["LifecycleError", "__version__", "activate", "add_feedback", "attach_candidate_package", "attest_release", "build", "check_version", "create_change_proposal", "create_diff", "create_release_candidate", "evaluate_change", "execute_activation", "init_environment", "init_registry", "inspect_feedback", "plan_regression", "propose_activation", "publish_release", "record_review", "register_consumer", "review_activation", "rollback", "run_regression", "submit_change_proposal", "validate", "verify"]
