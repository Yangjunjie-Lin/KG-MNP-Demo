"""Ontology release policy tests."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "ontology-release-policy.yaml"


def _load() -> dict:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_semantic_versioning_declared():
    data = _load()
    assert data["versioning_scheme"] == "semantic-versioning"


def test_change_classes_defined():
    classes = _load()["change_classification"]
    for key in ("major", "minor", "patch"):
        assert key in classes
        assert isinstance(classes[key], list)
        assert classes[key]
        assert len(classes[key]) == len(set(classes[key]))


def test_approval_and_artifact_guards():
    data = _load()
    approval = data["approval"]
    assert approval["schema_delta_requires_review"] is True
    assert approval["tbox_publication_scope_required"] is True
    assert approval["rationale_required"] is True
    assert approval["evidence_required"] is True
    assert approval["compatibility_assessment_required"] is True

    artifacts = data["generated_artifacts"]
    assert artifacts["direct_manual_edit_forbidden"] is True
    assert artifacts["regenerate_from_authoritative_inputs"] is True


def test_deprecation_policy_present():
    deprecation = _load()["deprecation"]
    assert deprecation["require_deprecated_marker"] is True
    assert deprecation["require_replacement_term_when_available"] is True
    assert deprecation["require_change_log"] is True
    assert deprecation["immediate_removal_forbidden"] is True
