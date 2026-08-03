from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OntologySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    module_count: int | None = None
    module_count_all: int | None = None
    class_count: int | None = None
    object_property_count: int | None = None
    data_property_count: int | None = None
    runtime_files: list[str] = Field(default_factory=list)


class OntologyModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    module: str
    label_zh: str | None = None
    label_en: str | None = None
    description: str | None = None
    classes: list[str] = Field(default_factory=list)
    object_properties: list[str] = Field(default_factory=list)
    data_properties: list[str] = Field(default_factory=list)


class OntologyClassResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    iri: str | None = None
    local_name: str
    label: str | None = None
    module: str | None = None
    type: str | None = "Class"


class OntologyPropertyResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    iri: str | None = None
    local_name: str
    label: str | None = None
    module: str | None = None
    domain: list[str] = Field(default_factory=list)
    range: list[str] = Field(default_factory=list)


class OntologyGraphNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    label: str | None = None
    local_name: str | None = None
    type: str | None = None
    module: str | None = None


class OntologyGraphEdge(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    target: str
    predicate: str
    property_iri: str | None = None


class OntologyGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[OntologyGraphNode | dict[str, Any]] = Field(default_factory=list)
    edges: list[OntologyGraphEdge | dict[str, Any]] = Field(default_factory=list)


class OntologyModuleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OntologyModuleResponse | dict[str, Any]] = Field(default_factory=list)


class OntologyClassListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OntologyClassResponse | dict[str, Any]] = Field(default_factory=list)


class OntologyPropertiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_properties: list[OntologyPropertyResponse | dict[str, Any]] = Field(
        default_factory=list
    )
    data_properties: list[OntologyPropertyResponse | dict[str, Any]] = Field(
        default_factory=list
    )
