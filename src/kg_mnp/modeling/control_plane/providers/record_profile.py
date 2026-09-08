"""Closed data-only mixed-source profile shared by service and offline mapper."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProfileDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TypedField(ProfileDTO):
    predicate_iri: str = Field(min_length=1, max_length=500)
    datatype: Literal["string", "integer", "decimal", "boolean", "date", "dateTime"] = "string"


class IdentityAlias(ProfileDTO):
    value: str = Field(min_length=1, max_length=200)
    canonical: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=1000)


class IdentityReference(ProfileDTO):
    field: str = Field(min_length=1, max_length=100)
    target_space: str = Field(pattern=r"^[a-z][a-z0-9-]{0,50}$")
    predicate_iri: str = Field(min_length=1, max_length=500)


class RecordDefinition(ProfileDTO):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,50}$")
    class_iri: str = Field(min_length=1, max_length=500)
    identity_space: str = Field(pattern=r"^[a-z][a-z0-9-]{0,50}$")
    id_field: str = Field(min_length=1, max_length=100)
    identity_aliases: list[IdentityAlias] = Field(default_factory=list, max_length=1000)
    literals: dict[Annotated[str, Field(min_length=1, max_length=100)], TypedField] = Field(default_factory=dict, max_length=100)
    references: list[IdentityReference] = Field(default_factory=list, max_length=100)


class TableSelector(ProfileDTO):
    locator_kind: Literal["delimited-cell", "spreadsheet-cell", "document-table-cell"]
    sheet: str | None = Field(default=None, min_length=1, max_length=200)
    table_index: int | None = Field(default=None, ge=0, le=100000)


class MixedTable(RecordDefinition):
    source_id: str = Field(pattern=r"^urn:kg-mnp:source:[a-f0-9]{64}$")
    locator: TableSelector


class TextTemplate(RecordDefinition):
    source_id: str = Field(pattern=r"^urn:kg-mnp:source:[a-f0-9]{64}$")
    template: str = Field(min_length=1, max_length=4000)


class EvidenceSpan(ProfileDTO):
    field: str = Field(min_length=1, max_length=100)
    item_id: str = Field(pattern=r"^urn:kg-mnp:kg-ir-item:[a-f0-9]{64}$")
    start: int = Field(ge=0, le=1000000)
    end: int = Field(ge=1, le=1000000)
    quote: str = Field(min_length=1, max_length=10000)


class TextRecord(RecordDefinition):
    fields: list[EvidenceSpan] = Field(min_length=1, max_length=100)


class SourceExclusion(ProfileDTO):
    item_id: str = Field(pattern=r"^urn:kg-mnp:kg-ir-item:[a-f0-9]{64}$")
    rationale: str = Field(min_length=1, max_length=1000)


class MixedRecordMapping(ProfileDTO):
    profile: Literal["evidence-record-mapping-v2"]
    tables: list[MixedTable] = Field(default_factory=list, max_length=100)
    text_templates: list[TextTemplate] = Field(default_factory=list, max_length=100)
    text_records: list[TextRecord] = Field(default_factory=list, max_length=1000)
    exclusions: list[SourceExclusion] = Field(default_factory=list, max_length=10000)
