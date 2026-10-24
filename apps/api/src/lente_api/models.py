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
    integration_decision: Mapped[str | None] = mapped_column(String(40), index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str] = mapped_column(String(40), default="under_review", index=True)
    technical_owner: Mapped[str] = mapped_column(String(120), default="data-platform")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    catalog_import: Mapped[CatalogImport] = relationship()
    provider: Mapped[DataProvider] = relationship()
    source_resource: Mapped[SourceResource | None] = relationship()
    dataset: Mapped[Dataset | None] = relationship()


class EducationNetwork(Base):
    __tablename__ = "education_networks"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class EducationStage(Base):
    __tablename__ = "education_stages"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    display_order: Mapped[int] = mapped_column(Integer)


class EducationDependency(Base):
    __tablename__ = "education_dependencies"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    network_code: Mapped[str] = mapped_column(ForeignKey("education_networks.code"), index=True)


class School(Base):
    __tablename__ = "schools"

    inep_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SchoolVersion(Base):
    __tablename__ = "school_versions"
    __table_args__ = (
        UniqueConstraint("school_inep_code", "census_year", "release_id", name="uq_school_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    school_inep_code: Mapped[str] = mapped_column(ForeignKey("schools.inep_code"), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    census_year: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(260))
    state: Mapped[str] = mapped_column(String(2), index=True)
    dependency_code: Mapped[str] = mapped_column(
        ForeignKey("education_dependencies.code"), index=True
    )
    operating_status: Mapped[str] = mapped_column(String(40), index=True)
    location_type: Mapped[str | None] = mapped_column(String(30))
    infrastructure: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"))
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publication_releases.id"), index=True)


class EducationEnrollment(Base):
    __tablename__ = "education_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "school_inep_code",
            "census_year",
            "stage_code",
            "release_id",
            name="uq_education_enrollment_release",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    school_inep_code: Mapped[str] = mapped_column(ForeignKey("schools.inep_code"), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    census_year: Mapped[int] = mapped_column(Integer, index=True)
    stage_code: Mapped[str] = mapped_column(ForeignKey("education_stages.code"), index=True)
    dependency_code: Mapped[str] = mapped_column(
        ForeignKey("education_dependencies.code"), index=True
    )
    enrollment_count: Mapped[int | None] = mapped_column(Integer)
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"))
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publication_releases.id"), index=True)


class EducationMetric(Base):
    __tablename__ = "education_metrics"
    __table_args__ = (
        UniqueConstraint(
            "municipality_ibge_code",
            "reference_year",
            "metric_code",
            "network_code",
            "stage_code",
            "release_id",
            name="uq_education_metric_release",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    reference_year: Mapped[int] = mapped_column(Integer, index=True)
    metric_code: Mapped[str] = mapped_column(String(80), index=True)
    network_code: Mapped[str] = mapped_column(ForeignKey("education_networks.code"), index=True)
    stage_code: Mapped[str] = mapped_column(ForeignKey("education_stages.code"), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"))
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publication_releases.id"), index=True)


class Agency(Base):
    __tablename__ = "agencies"
    __table_args__ = (UniqueConstraint("source_system", "source_key", name="uq_agency_source_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(320))
    entity_identifier: Mapped[str | None] = mapped_column(String(32), index=True)
    unit_code: Mapped[str | None] = mapped_column(String(80))
    municipality_ibge_code: Mapped[str | None] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    state: Mapped[str | None] = mapped_column(String(2), index=True)
    power: Mapped[str | None] = mapped_column(String(40))
    sphere: Mapped[str | None] = mapped_column(String(40))


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("source_system", "source_key", name="uq_supplier_source_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(160))
    name: Mapped[str | None] = mapped_column(String(320))
    identifier_type: Mapped[str] = mapped_column(String(20))
    identifier: Mapped[str | None] = mapped_column(String(32), index=True)
    public_identity: Mapped[bool] = mapped_column(Boolean, default=False)
    privacy_review: Mapped[str] = mapped_column(String(80), default="pending")


class BudgetAccount(Base):
    __tablename__ = "budget_accounts"
    __table_args__ = (
        UniqueConstraint("source_system", "account_code", name="uq_budget_account_source_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    account_code: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(Text)
    account_type: Mapped[str | None] = mapped_column(String(60), index=True)
    hierarchy: Mapped[dict] = mapped_column(JSON, default=dict)


class FiscalStatement(Base):
    __tablename__ = "fiscal_statements"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_fiscal_statement_revision"
        ),
        Index(
            "ix_fiscal_statement_municipality_year_source",
            "municipality_ibge_code",
            "reference_year",
            "source_system",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agencies.id"), index=True)
    budget_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("budget_accounts.id"), index=True
    )
    statement_type: Mapped[str] = mapped_column(String(60), index=True)
    reference_year: Mapped[int] = mapped_column(Integer, index=True)
    reference_period: Mapped[int | None] = mapped_column(Integer, index=True)
    periodicity: Mapped[str | None] = mapped_column(String(30))
    annex: Mapped[str | None] = mapped_column(String(100))
    power: Mapped[str | None] = mapped_column(String(20))
    column_code: Mapped[str | None] = mapped_column(String(120))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Procurement(Base):
    __tablename__ = "procurements"
    __table_args__ = (
        UniqueConstraint("source_system", "source_key", "revision", name="uq_procurement_revision"),
        Index(
            "ix_procurement_municipality_year_status",
            "municipality_ibge_code",
            "procurement_year",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(180), index=True)
    municipality_ibge_code: Mapped[str | None] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id"), index=True)
    procurement_year: Mapped[int] = mapped_column(Integer, index=True)
    procurement_number: Mapped[str | None] = mapped_column(String(160))
    process_number: Mapped[str | None] = mapped_column(String(200))
    object_description: Mapped[str] = mapped_column(Text)
    modality_code: Mapped[str | None] = mapped_column(String(40), index=True)
    modality_name: Mapped[str | None] = mapped_column(String(160), index=True)
    status: Mapped[str | None] = mapped_column(String(160), index=True)
    sector: Mapped[str | None] = mapped_column(String(100), index=True)
    estimated_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    homologated_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    proposal_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposal_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ProcurementItem(Base):
    __tablename__ = "procurement_items"
    __table_args__ = (
        UniqueConstraint("procurement_id", "item_number", name="uq_procurement_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    procurement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procurements.id"), index=True)
    item_number: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    unit: Mapped[str | None] = mapped_column(String(100))
    estimated_unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    estimated_total_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("source_system", "source_key", "revision", name="uq_contract_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(180), index=True)
    procurement_source_key: Mapped[str | None] = mapped_column(String(180), index=True)
    municipality_ibge_code: Mapped[str | None] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    contract_year: Mapped[int] = mapped_column(Integer, index=True)
    contract_number: Mapped[str | None] = mapped_column(String(160))
    object_description: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(100), index=True)
    initial_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    global_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    signed_at: Mapped[date | None] = mapped_column(Date)
    validity_start: Mapped[date | None] = mapped_column(Date)
    validity_end: Mapped[date | None] = mapped_column(Date)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        UniqueConstraint("source_system", "source_key", "revision", name="uq_transfer_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(180), index=True)
    municipality_ibge_code: Mapped[str | None] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agencies.id"), index=True)
    program_code: Mapped[str | None] = mapped_column(String(100), index=True)
    program_name: Mapped[str | None] = mapped_column(String(240))
    reference_year: Mapped[int] = mapped_column(Integer, index=True)
    transfer_type: Mapped[str] = mapped_column(String(80), index=True)
    planned_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    source_document_url: Mapped[str] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class HealthEstablishment(Base):
    __tablename__ = "health_establishments"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_establishment_revision"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(160), index=True)
    cnes_code: Mapped[str] = mapped_column(String(7), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    name: Mapped[str] = mapped_column(String(320))
    facility_type_code: Mapped[str | None] = mapped_column(String(40), index=True)
    facility_type_name: Mapped[str | None] = mapped_column(String(240))
    management_scope: Mapped[str | None] = mapped_column(String(40))
    sus_linked: Mapped[bool | None] = mapped_column(Boolean, index=True)
    active: Mapped[bool | None] = mapped_column(Boolean, index=True)
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class HealthBed(Base):
    __tablename__ = "health_beds"
    __table_args__ = (
        UniqueConstraint("source_system", "source_key", "revision", name="uq_health_bed_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("health_establishments.id"), index=True
    )
    bed_type_code: Mapped[str] = mapped_column(String(60), index=True)
    bed_type_name: Mapped[str] = mapped_column(String(240))
    existing_count: Mapped[int | None] = mapped_column(Integer)
    sus_count: Mapped[int | None] = mapped_column(Integer)
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class HealthService(Base):
    __tablename__ = "health_services"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_service_revision"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("health_establishments.id"), index=True
    )
    service_code: Mapped[str] = mapped_column(String(60), index=True)
    service_name: Mapped[str] = mapped_column(String(320))
    classification_code: Mapped[str | None] = mapped_column(String(60))
    classification_name: Mapped[str | None] = mapped_column(String(320))
    sus_available: Mapped[bool | None] = mapped_column(Boolean, index=True)
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class HealthProduction(Base):
    __tablename__ = "health_production"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_production_revision"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    care_type: Mapped[str] = mapped_column(String(60), index=True)
    procedure_code: Mapped[str | None] = mapped_column(String(40), index=True)
    procedure_name: Mapped[str | None] = mapped_column(String(320))
    facility_type: Mapped[str | None] = mapped_column(String(160), index=True)
    sus_sector: Mapped[str | None] = mapped_column(String(80), index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class HealthEpidemiology(Base):
    __tablename__ = "health_epidemiology"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_epidemiology_revision"
        ),
        Index(
            "ix_health_epidemiology_municipality_period",
            "municipality_ibge_code",
            "period_start",
            "period_end",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    indicator_code: Mapped[str] = mapped_column(String(120), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    geography_basis: Mapped[str] = mapped_column(String(40), index=True)
    category_code: Mapped[str] = mapped_column(String(80), index=True)
    category_name: Mapped[str] = mapped_column(String(240))
    age_band: Mapped[str] = mapped_column(String(40), index=True)
    count: Mapped[int | None] = mapped_column(Integer)
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    disclosure_threshold: Mapped[int] = mapped_column(Integer)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class EconomicActivity(Base):
    __tablename__ = "economic_activities"
    __table_args__ = (
        UniqueConstraint("classification_system", "code", name="uq_economic_activity_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    classification_system: Mapped[str] = mapped_column(String(40), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(240))
    level: Mapped[str] = mapped_column(String(40))


class EconomyFact(Base):
    __tablename__ = "economy_facts"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_economy_fact_revision"
        ),
        Index("ix_economy_fact_municipality_year", "municipality_ibge_code", "reference_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    reference_year: Mapped[int] = mapped_column(Integer, index=True)
    metric_code: Mapped[str] = mapped_column(String(100), index=True)
    activity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("economic_activities.id"), index=True
    )
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    unit: Mapped[str] = mapped_column(String(80))
    price_basis: Mapped[str | None] = mapped_column(String(80))
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class LaborFact(Base):
    __tablename__ = "labor_facts"
    __table_args__ = (
        UniqueConstraint("source_system", "source_key", "revision", name="uq_labor_fact_revision"),
        Index("ix_labor_fact_municipality_period", "municipality_ibge_code", "period_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("economic_activities.id"), index=True)
    admissions: Mapped[int] = mapped_column(Integer)
    dismissals: Mapped[int] = mapped_column(Integer)
    balance: Mapped[int] = mapped_column(Integer)
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class SocialProgram(Base):
    __tablename__ = "social_programs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    provider: Mapped[str] = mapped_column(String(240))


class SocialBenefitFact(Base):
    __tablename__ = "social_benefit_facts"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_social_benefit_fact_revision"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_programs.id"), index=True)
    beneficiary_count: Mapped[int | None] = mapped_column(Integer)
    family_count: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class InfrastructureService(Base):
    __tablename__ = "infrastructure_services"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(240))
    service_type: Mapped[str] = mapped_column(String(60), index=True)


class InfrastructureFact(Base):
    __tablename__ = "infrastructure_facts"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_infrastructure_fact_revision"
        ),
        Index(
            "ix_infrastructure_fact_municipality_date", "municipality_ibge_code", "reference_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("infrastructure_services.id"), index=True
    )
    metric_code: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    unit: Mapped[str] = mapped_column(String(80))
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class AgricultureFact(Base):
    __tablename__ = "agriculture_facts"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_agriculture_fact_revision"
        ),
        Index(
            "ix_agriculture_fact_municipality_year",
            "municipality_ibge_code",
            "reference_year",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    municipality_ibge_code: Mapped[str] = mapped_column(
        ForeignKey("municipalities.ibge_code"), index=True
    )
    reference_year: Mapped[int] = mapped_column(Integer, index=True)
    product_code: Mapped[str] = mapped_column(String(40), index=True)
    product_name: Mapped[str] = mapped_column(String(240))
    metric_code: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    unit: Mapped[str] = mapped_column(String(80))
    availability_status: Mapped[str] = mapped_column(String(40), index=True)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class GeospatialAsset(Base):
    __tablename__ = "geospatial_assets"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_geospatial_asset_revision"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(40), index=True)
    source_key: Mapped[str] = mapped_column(String(240), index=True)
    geo_type: Mapped[str] = mapped_column(String(40), index=True)
    geo_code: Mapped[str] = mapped_column(String(40), index=True)
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    crs: Mapped[str] = mapped_column(String(40))
    geometry: Mapped[dict] = mapped_column(JSON)
    bbox: Mapped[list] = mapped_column(JSON, default=list)
    source_document_url: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


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


class ExportJob(Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'expired')",
            name="ck_export_jobs_status",
        ),
        CheckConstraint("format IN ('csv', 'parquet')", name="ck_export_jobs_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    requester_hash: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(60), index=True)
    format: Mapped[str] = mapped_column(String(20))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    row_limit: Mapped[int] = mapped_column(Integer)
    row_count: Mapped[int | None] = mapped_column(Integer)
    byte_count: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lock_token: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    error_details: Mapped[str | None] = mapped_column(Text)


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    issue_code: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="open")

    run: Mapped[IngestionRun] = relationship(back_populates="issues")
