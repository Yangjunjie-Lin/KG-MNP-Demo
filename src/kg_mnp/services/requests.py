"""Closed service DTOs, not a second Domain Contract catalogue."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import ServiceBoundaryError


class RequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyRequest(RequestDTO):
    pass


class ProjectCreateRequest(RequestDTO):
    name: str = Field(min_length=1, max_length=200)
    domain_pack: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    domain_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ProjectOpenRequest(RequestDTO):
    project_id: str | None = None


class PackInspectRequest(RequestDTO):
    pack_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


class JobRequest(RequestDTO):
    job_id: str = Field(pattern=r"^job_[a-f0-9]{32}$")


class PackageRequest(RequestDTO):
    package_id: str = Field(min_length=1, max_length=200)


class ReleaseRequest(RequestDTO):
    release_id: str = Field(min_length=1, max_length=200)


class EnvironmentRequest(RequestDTO):
    environment_id: str = Field(min_length=1, max_length=200)


REQUEST_MODELS = {
    "project.create": ProjectCreateRequest, "project.open": ProjectOpenRequest,
    "project.list": EmptyRequest, "project.validate": EmptyRequest, "project.lock": EmptyRequest,
    "domain-pack.discover": EmptyRequest, "domain-pack.inspect": PackInspectRequest,
    "job.get": JobRequest, "job.events": JobRequest, "operation.catalog": EmptyRequest,
    "registry.verify": EmptyRequest, "package.inspect": PackageRequest, "release.inspect": ReleaseRequest,
    "environment.inspect": EnvironmentRequest,
}


def validate_parameters(request):
    model = REQUEST_MODELS.get(request.operation_id)
    if model is None:
        raise ServiceBoundaryError("OPERATION_BLOCKED", "typed service request is not implemented", status_code=501)
    try:
        model.model_validate(request.parameters)
    except ValidationError as exc:
        # Avoid Pydantic's input echo, which may contain credentials or paths.
        raise ServiceBoundaryError("REQUEST_INVALID", "request does not match the operation contract", status_code=422) from exc
