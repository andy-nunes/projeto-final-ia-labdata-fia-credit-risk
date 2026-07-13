"""Testes pytest do pipeline operacional Silver."""

from pathlib import Path
import logging

import pandas as pd
import pytest

from scripts.data_sanitization import (
    collect_and_process,
    main,
    run_table_pipeline,
    staging_path,
    validate_staged,
    write_clean,
)
from scripts.silver_validations import SilverValidationError


class FakePipelineClient:
    """Simula MinIO para testar as três fronteiras do pipeline."""

    def __init__(self, source: pd.DataFrame) -> None:
        """Armazena a origem raw e chamadas realizadas."""
        self.source = source
        self.downloads: list[tuple[str, str]] = []
        self.uploads: list[tuple[str, str]] = []
        self.uploaded_frame: pd.DataFrame | None = None

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        """Materializa um CSV raw no caminho solicitado."""
        self.downloads.append((bucket, key))
        self.source.to_csv(filename, index=False)

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        """Captura o Parquet publicado no clean."""
        self.uploads.append((bucket, key))
        self.uploaded_frame = pd.read_parquet(filename)


def clean_pos_frame() -> pd.DataFrame:
    """Cria uma entrada POS pequena que passa pelo QA após transformação."""
    return pd.DataFrame(
        {"MONTHS_BALANCE": [-1], "SK_DPD": [0], "SK_DPD_DEF": [0]}
    )


def test_staging_path_is_run_specific_and_safe(tmp_path: Path) -> None:
    """Normaliza run_id e isola tabela e execução."""
    path = staging_path(
        "manual__2026-06-28T16:00:00+00:00",
        "POS_CASH_balance",
        tmp_path,
    )

    assert path.parents[3] == tmp_path
    assert ":" not in str(path)
    assert path.name == "POS_CASH_balance_silver.parquet"


def test_collect_processes_to_staging_without_clean_upload(
    tmp_path: Path,
    caplog,
) -> None:
    """Produz o intermediário e não publica antes da validação."""
    caplog.set_level(logging.INFO)
    client = FakePipelineClient(clean_pos_frame())

    metadata = collect_and_process(
        "POS_CASH_balance",
        "run-1",
        client=client,
        data_dir=tmp_path,
    )

    staged = Path(metadata["staging_path"])
    assert staged.exists()
    assert client.downloads == [("raw", "POS_CASH_balance.csv")]
    assert client.uploads == []
    assert metadata["rows"] == 1
    assert "coleta e processamento" in caplog.text.lower()


def test_validate_staged_logs_and_returns_small_metadata(tmp_path: Path, caplog) -> None:
    """Valida o Parquet intermediário sem escrever no MinIO."""
    caplog.set_level(logging.INFO)
    client = FakePipelineClient(clean_pos_frame())
    metadata = collect_and_process(
        "POS_CASH_balance", "run-2", client=client, data_dir=tmp_path
    )

    validated = validate_staged(metadata)

    assert validated["qa_status"] == "passed"
    assert validated["qa_passes"] == 3
    assert "[QA] POS_CASH_balance_silver.parquet" in caplog.text
    assert client.uploads == []


def test_failed_validation_preserves_staging(tmp_path: Path) -> None:
    """Mantém o arquivo intermediário para diagnóstico quando o QA reprova."""
    staged = tmp_path / "dirty.parquet"
    pd.DataFrame(
        {"MONTHS_BALANCE": [1], "SK_DPD": [-1], "SK_DPD_DEF": [-2]}
    ).to_parquet(staged, index=False)
    metadata = {
        "table_id": "POS_CASH_balance",
        "staging_path": str(staged),
        "clean_key": "POS_CASH_balance_silver.parquet",
        "rows": 1,
    }

    with pytest.raises(SilverValidationError):
        validate_staged(metadata)

    assert staged.exists()


def test_write_uploads_and_removes_only_table_staging(tmp_path: Path) -> None:
    """Publica no clean e remove o diretório da tabela após sucesso."""
    client = FakePipelineClient(clean_pos_frame())
    metadata = collect_and_process(
        "POS_CASH_balance", "run-3", client=client, data_dir=tmp_path
    )
    validated = validate_staged(metadata)
    sibling = Path(metadata["staging_path"]).parents[1] / "other" / "keep.txt"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("keep", encoding="utf-8")

    result = write_clean(validated, client=client)

    assert result["status"] == "uploaded"
    assert client.uploads == [("clean", "POS_CASH_balance_silver.parquet")]
    assert not Path(metadata["staging_path"]).parent.exists()
    assert sibling.exists()


def test_run_table_pipeline_executes_full_sequence(tmp_path: Path) -> None:
    """Executa coleta, QA e publicação na ordem garantida."""
    client = FakePipelineClient(clean_pos_frame())

    result = run_table_pipeline(
        "POS_CASH_balance", "cli-run", client=client, data_dir=tmp_path
    )

    assert result["status"] == "uploaded"
    assert client.uploaded_frame is not None


def test_main_continues_tables_and_returns_one_on_failure(mocker, capsys) -> None:
    """Relata falhas da CLI sem impedir o processamento das tabelas seguintes."""
    mocked = mocker.patch("scripts.data_sanitization.run_table_pipeline")
    mocked.side_effect = [RuntimeError("falha controlada"), {"status": "uploaded"}]

    exit_code = main(["bureau", "bureau_balance"])

    assert exit_code == 1
    assert mocked.call_count == 2
    assert "falha controlada" in capsys.readouterr().out
