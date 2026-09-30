"""Validação dos snapshots editáveis; o payload antigo do wizard é preservado."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from scripts.roadmap_builder import format_validation_errors, validate_config

NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Duration(StrictModel):
    value: int = Field(ge=1, le=36500)
    unit: Literal["days", "months"]


class DateFields(StrictModel):
    start: NonBlank
    end: NonBlank


class Schedule(StrictModel):
    project_start_date: str | None = None
    project_date_fields: DateFields = Field(
        default_factory=lambda: DateFields(start="Início previsto", end="Fim previsto")
    )
    milestone_durations: dict[str, Duration]


class Milestone(StrictModel):
    key: NonBlank
    title: NonBlank
    description: str = ""


class Label(StrictModel):
    name: NonBlank
    color: str = Field(pattern=r"^[0-9a-fA-F]{6}$")
    description: str = ""


class Issue(StrictModel):
    title: NonBlank
    milestone: NonBlank
    labels: list[NonBlank] = Field(default_factory=list)
    description: str = "Executar esta atividade conforme o processo da Fabrica de IA."
    entregaveis: list[NonBlank] = Field(
        default_factory=lambda: ["Evidencia principal anexada", "Criterios de aceite validados"],
        min_length=1,
    )
    criterios_aceite: list[NonBlank] = Field(
        default_factory=lambda: ["Resultado revisado com stakeholders", "Registro no Project atualizado"],
        min_length=1,
    )


class ProjectConfig(StrictModel):
    schedule: Schedule
    milestones: list[Milestone]
    labels: list[Label]
    issues: list[Issue]

    @model_validator(mode="after")
    def consistent_references(self):
        start = self.schedule.project_start_date
        if start is not None:
            try:
                if date.fromisoformat(start).isoformat() != start:
                    raise ValueError
            except ValueError:
                raise ValueError("project_start_date deve ser uma data válida AAAA-MM-DD.")
        errors = validate_config(self.model_dump())
        if errors:
            raise ValueError(format_validation_errors(errors))
        return self


class ConfigUpdate(StrictModel):
    base_version: int = Field(ge=1)
    change_note: NonBlank = Field(max_length=2000)
    config: ProjectConfig
    owner: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*$")] | None = None
    repo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_.-]+$")] | None = None
    title: NonBlank | None = Field(default=None, max_length=512)
    project_number: int | None = Field(default=None, ge=1)
    phase_keys: list[NonBlank] | None = None

    @model_validator(mode="after")
    def valid_phases(self):
        if self.repo in {".", ".."}:
            raise ValueError("Informe um nome de repositório válido.")
        if self.phase_keys is not None:
            known = {m.key for m in self.config.milestones}
            if not self.phase_keys or len(set(self.phase_keys)) != len(self.phase_keys):
                raise ValueError("phase_keys deve conter fases únicas ou ser null para todas.")
            if not set(self.phase_keys) <= known:
                raise ValueError("phase_keys referencia uma fase inexistente.")
        return self


class VersionRestore(StrictModel):
    base_version: int = Field(ge=1)
    change_note: NonBlank = Field(max_length=2000)
