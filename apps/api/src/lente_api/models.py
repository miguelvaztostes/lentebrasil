from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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


class CatalogImport(Base):
    __tablename__ = "catalog_imports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    catalog_name: Mapped[str] = mapped_column(String(160))
    catalog_version: Mapped[str] = mapped_column(String(80), index=True)
    schema_version: Mapped[str] = mapped_column(String(40))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_path: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    record_count: Mapped[int] = mapped_column(Integer)
    area_count: Mapped[int] = mapped_column(Integer)
    indicator_count: Mapped[int] = mapped_column(Integer)
    discrepancies: Mapped[list] = mapped_column(JSON, default=list)


class GeoUnit(Base):
    __tablename__ = "geo_units"
    __table_args__ = (
        CheckConstraint(
            "unit_type IN ('country', 'region', 'state', 'municipality')",
            name="ck_geo_units_type",
        ),
        UniqueConstraint("unit_type", "code", name="uq_geo_units_type_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("geo_units.id"), index=True)
    unit_type: Mapped[str] = mapped_column(String(40), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200), index=True)
    state: Mapped[str | None] = mapped_column(String(2))
    country_code: Mapped[str] = mapped_column(String(2), default="BR")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    parent: Mapped[GeoUnit | None] = relationship(remote_side="GeoUnit.id")


class GeoUnitVersion(Base):
    __tablename__ = "geo_unit_versions"
    __table_args__ = (
        UniqueConstraint("geo_unit_id", "effective_from", name="uq_geo_unit_version_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    geo_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("geo_units.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str | None] = mapped_column(String(2))
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_hash: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    geo_unit: Mapped[GeoUnit] = relationship()


class GeoCodeMapping(Base):
    __tablename__ = "geo_code_mappings"
    __table_args__ = (
        UniqueConstraint("code_system", "external_code", "valid_from", name="uq_geo_code_mapping"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    geo_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("geo_units.id"), index=True)
    code_system: Mapped[str] = mapped_column(String(60), index=True)
    external_code: Mapped[str] = mapped_column(String(64), index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    geo_unit: Mapped[GeoUnit] = relationship()


class DataProvider(Base):
    __tablename__ = "data_providers"
    __table_args__ = (
        CheckConstraint(
            "source_status IN ('discovered', 'pending_review', 'verified', 'unavailable', "
            "'restricted')",
            name="ck_data_providers_source_status",
        ),
        CheckConstraint(
            "connector_status IN ('not_implemented', 'planned', 'implemented', 'active', "
            "'degraded', 'failed', 'disabled')",
            name="ck_data_providers_connector_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    external_catalog_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    source_status: Mapped[str] = mapped_column(String(40), default="discovered", index=True)
    connector_status: Mapped[str] = mapped_column(String(40), default="not_implemented", index=True)
    license: Mapped[str | None] = mapped_column(String(200))
    terms: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    resources: Mapped[list[SourceResource]] = relationship(back_populates="provider")


class SourceResource(Base):
    __tablename__ = "source_resources"
    __table_args__ = (
        CheckConstraint(
            "format IN ('api', 'csv', 'zip', 'xlsx', 'parquet', 'portal', 'manual', "
            "'json', 'xml', 'pdf')",
            name="ck_source_resources_format",
        ),
        CheckConstraint(
            "source_status IN ('discovered', 'pending_review', 'verified', 'unavailable', "
            "'restricted')",
            name="ck_source_resources_source_status",
        ),
        CheckConstraint(
            "connector_status IN ('not_implemented', 'planned', 'implemented', 'active', "
            "'degraded', 'failed', 'disabled')",
            name="ck_source_resources_connector_status",
        ),
        CheckConstraint(
            "license_status IN ('unknown', 'pending_review', 'confirmed', 'restricted')",
            name="ck_source_resources_license_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_providers.id"), index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(260))
    external_catalog_id: Mapped[str | None] = mapped_column(String(180), unique=True)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    source_status: Mapped[str] = mapped_column(String(40), default="discovered", index=True)
    connector_status: Mapped[str] = mapped_column(String(40), default="not_implemented", index=True)
    license_status: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    license: Mapped[str | None] = mapped_column(String(200))
    terms: Mapped[str | None] = mapped_column(Text)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    provider: Mapped[DataProvider] = relationship(back_populates="resources")


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
    data_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_providers.id"), index=True
    )
    primary_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_resources.id"), index=True
    )
    catalog_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_imports.id"), index=True
    )
    external_catalog_id: Mapped[str | None] = mapped_column(String(180), unique=True)
    source_status: Mapped[str] = mapped_column(String(40), default="discovered", index=True)
    connector_status: Mapped[str] = mapped_column(String(40), default="not_implemented", index=True)
    catalog_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="source")
    data_provider: Mapped[DataProvider | None] = relationship()
    primary_resource: Mapped[SourceResource | None] = relationship()


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
    source_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_resources.id"), index=True
    )
    catalog_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_imports.id"), index=True
    )
    external_catalog_id: Mapped[str | None] = mapped_column(String(180), unique=True)
    connector_status: Mapped[str] = mapped_column(String(40), default="not_implemented", index=True)
    publication_status: Mapped[str] = mapped_column(String(40), default="not_published", index=True)
    catalog_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    source: Mapped[Source] = relationship(back_populates="datasets")
    snapshots: Mapped[list[SourceSnapshot]] = relationship(back_populates="dataset")
    runs: Mapped[list[IngestionRun]] = relationship(back_populates="dataset")
    source_resource: Mapped[SourceResource | None] = relationship()


class DatasetCoverage(Base):
    __tablename__ = "dataset_coverage"
    __table_args__ = (
        CheckConstraint(
            "coverage_status IN ('unknown', 'partial', 'complete', 'unavailable', "
            "'not_applicable')",
            name="ck_dataset_coverage_status",
        ),
        UniqueConstraint(
            "dataset_id", "geo_unit_id", "scope_key", name="uq_dataset_coverage_scope"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    geo_unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("geo_units.id"), index=True)
    scope_json: Mapped[dict] = mapped_column(JSON, default=dict)
    scope_key: Mapped[str] = mapped_column(String(64))
    coverage_status: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship()
    geo_unit: Mapped[GeoUnit | None] = relationship()


class PublicationRelease(Base):
    __tablename__ = "publication_releases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'withdrawn', 'failed')",
            name="ck_publication_releases_status",
        ),
        UniqueConstraint("dataset_id", "release_key", name="uq_publication_release_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    source_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_resources.id"), index=True
    )
    release_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    reference_start: Mapped[date | None] = mapped_column(Date)
    reference_end: Mapped[date | None] = mapped_column(Date)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship()
    source_resource: Mapped[SourceResource | None] = relationship()


class CatalogEntry(Base):
    __tablename__ = "catalog_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_catalog_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    catalog_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_imports.id"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_providers.id"), index=True)
    source_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_resources.id"), index=True
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("datasets.id"), index=True)
    area_slug: Mapped[str] = mapped_column(String(120), index=True)
    indicator_ref: Mapped[str] = mapped_column(String(180), index=True)
    indicator_refs: Mapped[list] = mapped_column(JSON, default=list)
    raw_record: Mapped[dict] = mapped_column(JSON)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    catalog_import: Mapped[CatalogImport] = relationship()
    provider: Mapped[DataProvider] = relationship()
    source_resource: Mapped[SourceResource | None] = relationship()
    dataset: Mapped[Dataset | None] = relationship()


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
        Index(
            "ix_observations_municipality_indicator_period",
            "municipality_ibge_code",
            "indicator_id",
            "period_start",
            "period_end",
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


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'retry', 'success', 'failed', 'disabled')",
            name="ck_ingestion_jobs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_key: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lock_token: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    dataset: Mapped[Dataset] = relationship()


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    issue_code: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="open")

    run: Mapped[IngestionRun] = relationship(back_populates="issues")
