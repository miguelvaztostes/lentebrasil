from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.transparency import (
    PncpProcurementAdapter,
    SiconfiStatementAdapter,
    TceSpExpenseAdapter,
    TceSpRevenueAdapter,
)


def _payload(
    content: bytes, *, url: str = "https://fonte.oficial.example/recurso"
) -> FetchedPayload:
    return FetchedPayload(
        content=content,
        url=url,
        fetched_at=datetime(2026, 10, 22, tzinfo=UTC),
        original_format="json",
    )


def _pncp_row(key: str, amount: str, updated: str) -> dict:
    return {
        "numeroControlePNCP": key,
        "anoCompra": 2026,
        "sequencialCompra": 424,
        "numeroCompra": "424",
        "processo": "2026/1",
        "objetoCompra": "Aquisição pública",
        "modalidadeId": 8,
        "modalidadeNome": "Dispensa",
        "situacaoCompraNome": "Divulgada no PNCP",
        "valorTotalEstimado": amount,
        "dataPublicacaoPncp": "2026-10-20T10:00:00",
        "dataAtualizacaoGlobal": updated,
        "orgaoEntidade": {"cnpj": "56024581000156", "razaoSocial": "Município"},
        "unidadeOrgao": {
            "codigoUnidade": "1",
            "nomeUnidade": "Prefeitura",
            "codigoIbge": "3543402",
            "ufSigla": "SP",
        },
    }


def test_pncp_paginates_and_exposes_resume_checkpoint(tmp_path: Path) -> None:
    adapter = PncpProcurementAdapter(
        raw_data_dir=tmp_path,
        selected_municipalities={"3543402"},
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 22),
        modalities=[8],
        update_mode=False,
    )
    responses = iter(
        [
            {
                "data": [_pncp_row("a", "950000.00", "2026-10-20T11:00:00")],
                "totalPaginas": 2,
                "numeroPagina": 1,
            },
            {
                "data": [_pncp_row("b", "15739.46", "2026-10-21T12:00:00")],
                "totalPaginas": 2,
                "numeroPagina": 2,
            },
        ]
    )

    def get_page(_path: str, _parameters: dict) -> httpx.Response:
        adapter.pages_fetched += 1
        return httpx.Response(
            200,
            content=json.dumps(next(responses)).encode(),
            request=httpx.Request("GET", "https://pncp.gov.br/api/consulta/v1/test"),
        )

    adapter._get_page = get_page  # type: ignore[method-assign]
    payloads = adapter.fetch()
    records = [record for payload in payloads for record in adapter.parse(payload)]
    assert len(payloads) == 2
    assert [record.estimated_amount for record in records] == [
        Decimal("950000.00"),
        Decimal("15739.46"),
    ]
    assert adapter.checkpoint_metadata() == {
        "window_end": "2026-10-22",
        "last_source_updated_at": "2026-10-21T12:00:00+00:00",
        "last_source_key": "b",
        "pages_fetched": 2,
    }


def test_siconfi_keeps_three_rows_and_exact_decimals(tmp_path: Path) -> None:
    adapter = SiconfiStatementAdapter(
        raw_data_dir=tmp_path,
        statement_type="rgf",
        municipality_codes=["3543402"],
        years=[2025],
        periods=[3],
        annex="RGF-Anexo 01",
        sleep_fn=lambda _seconds: None,
    )
    base = {
        "exercicio": 2025,
        "cod_ibge": 3543402,
        "periodo": 3,
        "periodicidade": "Q",
        "anexo": "RGF-Anexo 01",
        "co_poder": "E",
        "instituicao": "Município de Ribeirão Preto",
        "conta": "Despesa com pessoal",
        "rotulo": "Total",
    }
    rows = [
        {**base, "cod_conta": f"conta-{index}", "coluna": f"coluna-{index}", "valor": value}
        for index, value in enumerate(["1.10", "2.20", None], start=1)
    ]
    records = adapter.parse(_payload(json.dumps({"items": rows}).encode()))
    adapter.validate(records)
    assert [record.amount for record in records] == [Decimal("1.10"), Decimal("2.20"), None]
    assert len({record.source_key for record in records}) == 3


def test_tcesp_csv_preserves_rubric_and_does_not_turn_missing_into_zero(tmp_path: Path) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=TceSpRevenueAdapter.expected_headers, delimiter=";")
    writer.writeheader()
    common = {header: "" for header in TceSpRevenueAdapter.expected_headers}
    common.update(
        {
            "ano_exercicio": "2025",
            "ds_municipio": "Ribeirão Preto",
            "ds_orgao": "Prefeitura Municipal",
            "mes_referencia": "1",
            "ds_poder": "Executivo",
            "ds_tipo": "111000000 - Impostos",
        }
    )
    writer.writerow(
        {**common, "id_rec_arrec_detalhe": "43685502", "vl_arrecadacao": "6.798.979,01"}
    )
    writer.writerow({**common, "id_rec_arrec_detalhe": "43685503", "vl_arrecadacao": "266.487,61"})
    writer.writerow({**common, "id_rec_arrec_detalhe": "43685504", "vl_arrecadacao": ""})
    archive_path = tmp_path / "receitas.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("receitas-2025.csv", buffer.getvalue().encode("cp1252"))
    payload = FetchedPayload(
        content=None,
        file_path=archive_path,
        url="https://transparencia.tce.sp.gov.br/conjunto-de-dados/receitas-2025.zip",
        fetched_at=datetime(2026, 10, 22, tzinfo=UTC),
        original_format="csv.zip",
        resource_version="exercise:2025",
    )
    adapter = TceSpRevenueAdapter(
        raw_data_dir=tmp_path,
        years=[2025],
        municipality_names={"RIBEIRAO PRETO": "3543402"},
    )
    records = adapter.parse(payload)
    adapter.validate(records)
    assert [record.amount for record in records] == [
        Decimal("6798979.01"),
        Decimal("266487.61"),
        None,
    ]
    assert all(record.account_code == "111000000" for record in records)


def test_tcesp_expenses_aggregate_phases_and_discard_supplier_data(tmp_path: Path) -> None:
    adapter = TceSpExpenseAdapter(
        raw_data_dir=tmp_path,
        municipalities={"3543402": "Ribeirão Preto"},
        years=[2025],
        months=[1],
        max_requests=1,
    )
    municipalities = [{"municipio": "ribeirao-preto", "municipio_extenso": "Ribeirão Preto"}]
    common = {
        "orgao": "Prefeitura Municipal",
        "mes": "Janeiro",
        "nr_empenho": "1-2025",
        "id_fornecedor": "PESSOA FÍSICA - 123456",
        "nm_fornecedor": "NOME QUE NÃO PODE SER PERSISTIDO",
        "dt_emissao_despesa": "02/01/2025",
    }
    expenses = [
        {**common, "evento": "Empenhado", "vl_despesa": "100,10"},
        {**common, "evento": "Empenhado", "vl_despesa": "20,20"},
        {**common, "evento": "Valor Liquidado", "vl_despesa": "80,05"},
        {**common, "evento": "Valor Pago", "vl_despesa": "60,01"},
        {**common, "evento": "Reforço", "vl_despesa": "5,00"},
        {**common, "evento": "Anulação", "vl_despesa": "2,00"},
    ]

    def get(url: str, *, timeout: float = 60) -> httpx.Response:
        body = municipalities if url.endswith("/municipios") else expenses
        return httpx.Response(
            200,
            content=json.dumps(body, ensure_ascii=False).encode(),
            request=httpx.Request("GET", url),
            headers={"content-type": "application/json"},
        )

    adapter.get = get  # type: ignore[method-assign]
    adapter.discover()
    payload = adapter.fetch()[0]
    assert b"NOME QUE" not in payload.read_bytes()
    assert b"123456" not in payload.read_bytes()
    assert payload.response_headers["x-lente-personal-fields"] == "discarded-before-snapshot"
    records = adapter.parse(payload)
    adapter.validate(records)
    amounts = {record.column_code: record.amount for record in records}
    assert amounts == {
        "annulment": Decimal("2.00"),
        "committed": Decimal("120.30"),
        "liquidated": Decimal("80.05"),
        "paid": Decimal("60.01"),
        "reinforcement": Decimal("5.00"),
    }
    assert next(record for record in records if record.column_code == "committed").hierarchy == {
        "source_rows": 2
    }


def test_tcesp_expense_empty_month_remains_absent_instead_of_zero(tmp_path: Path) -> None:
    adapter = TceSpExpenseAdapter(
        raw_data_dir=tmp_path,
        municipalities={"3543402": "Ribeirão Preto"},
        years=[2025],
        months=[2],
        max_requests=1,
    )
    payload = _payload(
        json.dumps(
            {
                "municipality_code": "3543402",
                "year": 2025,
                "month": 2,
                "phases": [],
                "source_rows": 0,
            }
        ).encode()
    )
    records = adapter.parse(payload)
    adapter.validate(records)
    assert records == []
