"""Testes pytest das fronteiras operacionais do pipeline Gold."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.abt_transform import (
    main,
    process_application,
    stage_path,
    validate_application_stage,
    validate_pos_cash_stage,
    write_abt,
)
from scripts.gold_validations import GoldValidationError


class FakeGoldClient:
    """Simula downloads clean e captura o único upload ABT."""

    def __init__(self, frames: dict[str, pd.DataFrame] | None = None) -> None:
        """Armazena Parquets por chave e chamadas realizadas."""
        self.frames = frames or {}
        self.downloads: list[tuple[str, str]] = []
        self.uploads: list[tuple[str, str]] = []
        self.uploaded: pd.DataFrame | None = None

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        """Materializa uma entrada clean no caminho temporário."""
        self.downloads.append((bucket, key))
        self.frames[key].to_parquet(filename, index=False)

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        """Captura a ABT enviada ao destino final."""
        self.uploads.append((bucket, key))
        self.uploaded = pd.read_parquet(filename)


def test_process_and_validate_application_use_local_staging(tmp_path: Path) -> None:
    """Baixa do clean e transporta somente metadados pequenos."""
    client = FakeGoldClient(
        {
            "application_train_silver.parquet": pd.DataFrame(
                {"SK_ID_CURR": [1, 2], "TARGET": [0, 1]}
            )
        }
    )

    metadata = process_application("manual:run+1", client, tmp_path)
    validated = validate_application_stage(metadata)

    assert client.downloads == [("clean", "application_train_silver.parquet")]
    assert Path(metadata["staging_path"]).is_file()
    assert ":" not in metadata["staging_path"]
    assert metadata["rows"] == 2
    assert validated["qa_status"] == "passed"
    assert all(not isinstance(value, pd.DataFrame) for value in validated.values())


def test_failed_validation_preserves_staging(tmp_path: Path) -> None:
    """Mantém o agregado local quando o QA reprova a etapa."""
    application = stage_path("run-fail", "application", tmp_path)
    application.parent.mkdir(parents=True)
    pd.DataFrame({"SK_ID_CURR": [1], "TARGET": [0]}).to_parquet(
        application, index=False
    )
    staged = stage_path("run-fail", "pos_cash", tmp_path)
    staged.parent.mkdir(parents=True)
    pd.DataFrame(
        {"SK_ID_CURR": [2], "POS_SK_DPD_MAX": [-1], "POS_RATE_DPD": [2.0]}
    ).to_parquet(staged, index=False)
    metadata = {
        "stage": "pos_cash",
        "run_id": "run-fail",
        "staging_path": str(staged),
        "rows": 1,
    }

    with pytest.raises(GoldValidationError):
        validate_pos_cash_stage(metadata, tmp_path)

    assert staged.exists()


def test_write_abt_requires_qa_uploads_final_and_cleans_run(tmp_path: Path) -> None:
    """Publica somente ABT aprovada e remove todo o staging do run."""
    staged = stage_path("run-ok", "abt_final", tmp_path)
    staged.parent.mkdir(parents=True)
    pd.DataFrame({"SK_ID_CURR": [1], "TARGET": [0]}).to_parquet(staged, index=False)
    metadata = {
        "stage": "abt_final",
        "run_id": "run-ok",
        "staging_path": str(staged),
        "rows": 1,
    }
    client = FakeGoldClient()

    with pytest.raises(ValueError, match="QA"):
        write_abt(metadata, client)
    assert staged.exists()

    result = write_abt({**metadata, "qa_status": "passed"}, client)

    assert client.uploads == [("abt", "abt_train.parquet")]
    assert result["destination"] == "abt/abt_train.parquet"
    assert not tmp_path.joinpath(".gold_staging", "run-ok").exists()


def test_main_reports_failure_and_returns_one(mocker, capsys) -> None:
    """Converte falha sequencial em código de saída para o shell."""
    mocker.patch(
        "scripts.abt_transform.run_gold_pipeline",
        side_effect=RuntimeError("falha controlada"),
    )

    assert main([]) == 1
    output = capsys.readouterr().out
    assert "[FAIL]" in output
    assert "falha controlada" in output
