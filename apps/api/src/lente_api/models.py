from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Municipality(Base):
    __tablename__ = "municipalities"

    ibge_code: Mapped[str] = mapped_column(String(7), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(2))


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    source_url: Mapped[str] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(String(200))
    terms: Mapped[str | None] = mapped_column(Text)
    expected_frequency: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="source")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(80), index=True)
    granularity: Mapped[str] = mapped_column(String(160))
    update_policy: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), index=True)

    source: Mapped[Source] = relationship(back_populates="datasets")
    snapshots: Mapped[list[SourceSnapshot]] = relationship(back_populates="dataset")
    runs: Mapped[list[IngestionRun]] = relationship(back_populates="dataset")


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    url: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str | None] = mapped_column(Text)
    original_format: Mapped[str] = mapped_column(String(40))
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)

    dataset: Mapped[Dataset] = relationship(back_populates="snapshots")


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(240))
    definition: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(80))
    periodicity: Mapped[str] = mapped_column(String(80))
    methodology: Mapped[str] = mapped_column(Text)
    disaggregation_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    limitations: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(80), index=True)
    direction: Mapped[str | None] = mapped_column(String(40))


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint(
            "municipality_ibge_code",
            "indicator_id",
            "period_start",
            "period_end",
            "scope_key",
            "revision",
            name="uq_observation_logical_revision",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    indicator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("indicators.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    scope_json: Mapped[dict] = mapped_column(JSON, default=dict)
    scope_key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"))
    source_reference_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)

    municipality: Mapped[Municipality] = relationship()
    indicator: Mapped[Indicator] = relationship()
    snapshot: Mapped[SourceSnapshot] = relationship()


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), index=True)
    items_received: Mapped[int] = mapped_column(Integer, default=0)
    items_accepted: Mapped[int] = mapped_column(Integer, default=0)
    items_rejected: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64))
    error_details: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship(back_populates="runs")
    issues: Mapped[list[DataQualityIssue]] = relationship(back_populates="run")


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    issue_code: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="open")

    run: Mapped[IngestionRun] = relationship(back_populates="issues")
