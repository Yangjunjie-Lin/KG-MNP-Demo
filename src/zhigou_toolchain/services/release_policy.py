"""Resolve the explicit server review profile into a digest-bound release gate.

The original bundled policy remains byte-compatible. The effective policy ID
binds its content and the service profile, including the development exception.
Clients cannot provide or weaken these fields.
"""
from zhigou_toolchain.contracts.canonical import stable_urn
from zhigou_toolchain.lifecycle.policy import load_policy

from .errors import ServiceBoundaryError


def release_policy(profile: str) -> dict:
    base = load_policy("release-policy-1.0.0.yaml")
    if profile not in {"PRODUCTION_MULTI_ROLE", "DEVELOPMENT_SINGLE_REVIEWER"}:
        raise ValueError("unknown release review profile")
    development = profile == "DEVELOPMENT_SINGLE_REVIEWER"
    fields = {
        "required_roles": ["RELEASE_MANAGER"] if development else base["review_roles"],
        "minimum_distinct_reviewers": 1 if development else 2,
    }
    return {**fields, "release_policy_id": stable_urn("release-policy", {
        "base_policy_id": base["policy_id"], "base_content_digest": base["content_digest"],
        "profile": profile, "development_only": development, **fields,
    })}


def require_release_policy(candidate: dict, profile: str) -> None:
    for field, value in release_policy(profile).items():
        actual = candidate.get(field)
        if field == "required_roles":
            actual, value = sorted(actual or []), sorted(value)
        if actual != value:
            raise ServiceBoundaryError("RELEASE_POLICY_STALE", "candidate does not match the current server review policy", status_code=409)
