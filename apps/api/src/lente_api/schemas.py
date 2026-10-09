from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MunicipalityOut(OrmModel):
    ibge_code: str
    name: str
    state: str


class IndicatorOut(OrmModel):
    code: str
    label: str
    definition: str
    unit: str
    periodicity: str
    methodology: str
    disaggregation_schema: dict[str, Any]
    limitations: str
    domain: str
    direction: str | None


class ObservationOut(BaseModel):
    period_start: date
    period_end: date
    scope: dict[str, Any]
    value: Decimal | None
    availability_status: str
    revision: int
    source_reference_at: datetime | None
    retrieved_at: datetime
    source: dict[str, Any]


class PaginatedResponse(BaseModel):
    items: list[Any]
    count: int
    limit: int
    offset: int
