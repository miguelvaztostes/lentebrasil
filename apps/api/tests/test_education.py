from __future__ import annotations

import csv
import io
import os
import uuid
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.education import (
    InepCensoEscolarAdapter,
    InepIdebAdapter,
    MetricRecord,
    SchoolRecord,
    rollback_education_release,
)
from ingestion.adapters.federal_education import FndePnaeAdapter, InepSaebAdapter
from openpyxl import Workbook
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from lente_api.models import (
    Dataset,
    EducationEnrollment,
    EducationMetric,
    PublicationRelease,
    School,
    SchoolVersion,
    SourceSnapshot,
)


def _payload(path: Path) -> FetchedPayload:
    return FetchedPayload(
        content=None,
        file_path=path,
        url="https://download.inep.gov.br/fixture.zip",
        fetched_at=datetime.now(UTC),
        original_format="zip",
    )


def test_censo_parser_whitelists_public_school_fields_and_totals(tmp_path: Path) -> None:
    adapter = InepCensoEscolarAdapter(raw_data_dir=tmp_path, selected_municipalities={"3543402"})
    fields = [
        "NU_ANO_CENSO",
        "SG_UF",
        "CO_MUNICIPIO",
        "NO_ENTIDADE",
        "CO_ENTIDADE",
        "TP_DEPENDENCIA",
        "TP_SITUACAO_FUNCIONAMENTO",
        "TP_LOCALIZACAO",
        *adapter.stages.values(),
        *adapter.infrastructure_fields.values(),
        "NU_TELEFONE",
    ]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
    writer.writeheader()
    row = {field: "1" for field in fields}
    row.update(
        {
            "NU_ANO_CENSO": "2024",
            "SG_UF": "SP",
            "CO_MUNICIPIO": "3543402",
            "NO_ENTIDADE": "ESCOLA OFICIAL",
            "CO_ENTIDADE": "35000001",
            "TP_DEPENDENCIA": "3",
            "TP_SITUACAO_FUNCIONAMENTO": "1",
            "QT_MAT_BAS": "120",
            "QT_MAT_INF": "...",
            "NU_TELEFONE": "1633330000",
        }
    )
    writer.writerow(row)
    path = tmp_path / "censo.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "microdados/dados/microdados_ed_basica_2024.csv", stream.getvalue().encode("cp1252")
        )
    records = adapter.parse(_payload(path))
    adapter.validate(records)
    assert len(records) == 1
    assert records[0].enrollments["all_basic"] == 120
    assert records[0].enrollments["early_childhood"] is None
    assert "telefone" not in records[0].infrastructure
    assert records[0].municipality_code == "3543402"


def test_ideb_parser_preserves_suppression_and_network(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for _ in range(9):
        sheet.append([])
    headers = [
        "SG_UF",
        "CO_MUNICIPIO",
        "NO_MUNICIPIO",
        "REDE",
        "VL_OBSERVADO_2025",
        "VL_INDICADOR_REND_2025",
        "VL_NOTA_MATEMATICA_2025",
        "VL_NOTA_PORTUGUES_2025",
        "VL_NOTA_MEDIA_2025",
    ]
    sheet.append(headers)
    sheet.append(["SP", 3543402, "Ribeirão Preto", "Municipal", "-", 0.97, 240.1, 232.2, 5.1])
    xlsx = io.BytesIO()
    workbook.save(xlsx)
    path = tmp_path / "ideb.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("divulgacao.xlsx", xlsx.getvalue())
    adapter = InepIdebAdapter(raw_data_dir=tmp_path, selected_municipalities={"3543402"})
    records = adapter.parse(_payload(path))
    adapter.validate(records)
    ideb = next(item for item in records if item.metric_code == "ideb")
    math = next(item for item in records if item.metric_code == "saeb_mathematics")
    assert ideb.value is None and ideb.availability_status == "suppressed"
    assert math.value == Decimal("240.1")
    assert math.network_code == "municipal"


def test_saeb_parser_keeps_only_total_location_and_preserves_suppression(tmp_path: Path) -> None:
    adapter = InepSaebAdapter(raw_data_dir=tmp_path, selected_municipalities={"3543402"})
    headers = [
        "ANO_SAEB",
        "CO_MUNICIPIO",
        "DEPENDENCIA_ADM",
        "LOCALIZACAO",
        *adapter.metrics,
    ]
    records = adapter.parse_rows(
        [
            headers,
            [2023, 3543402, "Municipal", "Total", 211.07, 221.4, 249.86, 250.17, None, "-"],
            [2023, 3543402, "Municipal", "Urbana", 999, 999, 999, 999, 999, 999],
        ]
    )
    adapter.validate(records)
    assert len(records) == 6
    assert {item.stage_code for item in records} == {
        "fundamental_year_5",
        "fundamental_year_9",
        "secondary_year_3",
    }
    secondary = [item for item in records if item.stage_code == "secondary_year_3"]
    assert all(
        item.value is None and item.availability_status == "suppressed" for item in secondary
    )


def test_pnae_parser_reconciles_municipality_and_brazilian_numbers(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["DIRETORIA"])
    sheet.append(["COORDENAÇÃO"])
    sheet.append(["Previsão Repasse Financeiro PNAE - 2024"])
    sheet.append(["Ano: 2024"])
    sheet.append(["UF", "ENTIDADE_RESP", "ACAO", "QTDE_ALUNO", "VALOR_PREVISTO"])
    sheet.append(["SP", "PREF MUN DE RIBEIRAO PRETO", "PNACN", "12.531", "3.433.494,00"])
    sheet.append(["SP", "SECRETARIA DE EDUCACAO DO ESTADO DE SAO PAULO", "PNACN", 1, 1])
    path = tmp_path / "pnae.xlsx"
    workbook.save(path)
    adapter = FndePnaeAdapter(
        raw_data_dir=tmp_path,
        selected_municipalities={"3543402"},
        municipality_names={("SP", "RIBEIRAO PRETO"): "3543402"},
    )
    records = adapter.parse(_payload(path))
    adapter.validate(records)
    assert len(records) == 2
    students = next(item for item in records if item.metric_code == "pnae_students_planned")
    transfer = next(item for item in records if item.metric_code == "pnae_transfer_planned_brl")
    assert students.value == Decimal("12531")
    assert transfer.value == Decimal("3433494.00")
    assert transfer.stage_code == "pnae_daycare"


@pytest.mark.integration
def test_education_release_rollback_restores_previous_release() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    engine = create_engine(url)
    release_ids: list[uuid.UUID] = []
    with Session(engine) as db:
        dataset = db.scalar(select(Dataset).where(Dataset.code == "inep_ideb_municipal"))
        assert dataset is not None
        old = PublicationRelease(
            dataset_id=dataset.id,
            release_key=f"test-old-{uuid.uuid4()}",
            status="withdrawn",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            provenance={},
        )
        new = PublicationRelease(
            dataset_id=dataset.id,
            release_key=f"test-new-{uuid.uuid4()}",
            status="published",
            published_at=datetime(2026, 2, 1, tzinfo=UTC),
            provenance={},
        )
        db.add_all([old, new])
        db.commit()
        release_ids = [old.id, new.id]
        restored = rollback_education_release(db, dataset.code, new.release_key)
        assert restored == old.release_key
        assert db.get(PublicationRelease, old.id).status == "published"
        assert db.get(PublicationRelease, new.id).status == "withdrawn"
    with Session(engine) as db:
        db.execute(delete(PublicationRelease).where(PublicationRelease.id.in_(release_ids)))
        db.commit()


@pytest.mark.integration
def test_censo_publication_orders_parent_rows_and_is_idempotent(tmp_path: Path) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    engine = create_engine(url)
    school_code = "35999998"
    snapshot_id = release_id = None
    previous_release_ids: list[uuid.UUID] = []
    original_publication_status = "not_published"
    with Session(engine) as db:
        dataset = db.scalar(select(Dataset).where(Dataset.code == "inep_censo_escolar"))
        assert dataset is not None
        original_publication_status = dataset.publication_status
        previous_release_ids = list(
            db.scalars(
                select(PublicationRelease.id).where(
                    PublicationRelease.dataset_id == dataset.id,
                    PublicationRelease.status == "published",
                )
            )
        )
        adapter = InepCensoEscolarAdapter(
            raw_data_dir=tmp_path, selected_municipalities={"3543402"}
        )
        payload = FetchedPayload(
            content=b"fixture-censo-release",
            url="https://download.inep.gov.br/fixture.zip",
            fetched_at=datetime.now(UTC),
            original_format="zip",
            persist_raw=False,
        )
        snapshot = adapter._create_snapshot(db, dataset, payload)
        record = SchoolRecord(
            inep_code=school_code,
            municipality_code="3543402",
            year=2024,
            name="ESCOLA DE TESTE",
            state="SP",
            dependency_code="3",
            operating_status="1",
            location_type="urban",
            infrastructure={"internet": True},
            enrollments={"all_basic": 10},
        )
        adapter.upsert(db, [record], snapshot)
        adapter.upsert(db, [record], snapshot)
        db.commit()
        release = db.scalar(
            select(PublicationRelease).where(
                PublicationRelease.dataset_id == dataset.id,
                PublicationRelease.release_key == f"2024-{payload.sha256[:16]}",
            )
        )
        assert release is not None
        assert (
            db.scalar(
                select(func.count(SchoolVersion.id)).where(
                    SchoolVersion.school_inep_code == school_code
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count(EducationEnrollment.id)).where(
                    EducationEnrollment.school_inep_code == school_code
                )
            )
            == 1
        )
        snapshot_id, release_id = snapshot.id, release.id
    with Session(engine) as db:
        db.execute(
            delete(EducationEnrollment).where(EducationEnrollment.school_inep_code == school_code)
        )
        db.execute(delete(SchoolVersion).where(SchoolVersion.school_inep_code == school_code))
        db.execute(delete(School).where(School.inep_code == school_code))
        db.execute(delete(PublicationRelease).where(PublicationRelease.id == release_id))
        db.execute(delete(SourceSnapshot).where(SourceSnapshot.id == snapshot_id))
        for previous_id in previous_release_ids:
            previous = db.get(PublicationRelease, previous_id)
            if previous is not None:
                previous.status = "published"
        dataset = db.scalar(select(Dataset).where(Dataset.code == "inep_censo_escolar"))
        assert dataset is not None
        dataset.publication_status = original_publication_status
        db.commit()


@pytest.mark.integration
def test_pnae_metric_publication_is_idempotent(tmp_path: Path) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    engine = create_engine(url)
    snapshot_id = release_id = None
    previous_release_ids: list[uuid.UUID] = []
    original_publication_status = "not_published"
    with Session(engine) as db:
        dataset = db.scalar(select(Dataset).where(Dataset.code == "fnde_pnae_municipal"))
        assert dataset is not None
        original_publication_status = dataset.publication_status
        previous_release_ids = list(
            db.scalars(
                select(PublicationRelease.id).where(
                    PublicationRelease.dataset_id == dataset.id,
                    PublicationRelease.status == "published",
                )
            )
        )
        adapter = FndePnaeAdapter(
            raw_data_dir=tmp_path,
            selected_municipalities={"3543402"},
            municipality_names={("SP", "RIBEIRAO PRETO"): "3543402"},
        )
        payload = FetchedPayload(
            content=b"fixture-pnae-release",
            url="https://www.gov.br/fnde/fixture.xlsx",
            fetched_at=datetime.now(UTC),
            original_format="xlsx",
            persist_raw=False,
        )
        snapshot = adapter._create_snapshot(db, dataset, payload)
        record = MetricRecord(
            "3543402",
            2024,
            "pnae_transfer_planned_brl",
            "municipal",
            "pnae_daycare",
            Decimal("3433494.00"),
            "available",
        )
        adapter.upsert(db, [record], snapshot)
        adapter.upsert(db, [record], snapshot)
        db.commit()
        release = db.scalar(
            select(PublicationRelease).where(
                PublicationRelease.dataset_id == dataset.id,
                PublicationRelease.release_key == f"2024-{payload.sha256[:16]}",
            )
        )
        assert release is not None
        assert (
            db.scalar(
                select(func.count(EducationMetric.id)).where(
                    EducationMetric.release_id == release.id
                )
            )
            == 1
        )
        snapshot_id, release_id = snapshot.id, release.id
    with Session(engine) as db:
        db.execute(delete(EducationMetric).where(EducationMetric.release_id == release_id))
        db.execute(delete(PublicationRelease).where(PublicationRelease.id == release_id))
        db.execute(delete(SourceSnapshot).where(SourceSnapshot.id == snapshot_id))
        for previous_id in previous_release_ids:
            previous = db.get(PublicationRelease, previous_id)
            if previous is not None:
                previous.status = "published"
        dataset = db.scalar(select(Dataset).where(Dataset.code == "fnde_pnae_municipal"))
        assert dataset is not None
        dataset.publication_status = original_publication_status
        db.commit()
