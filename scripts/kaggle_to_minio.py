"""Funcoes para baixar dados Kaggle e substituir arquivos no MinIO."""

from pathlib import Path
from tempfile import TemporaryDirectory
import os

import boto3
import kagglehub
from botocore.client import Config


COMPETITION_NAME = "home-credit-default-risk"
RAW_BUCKET = os.getenv("RAW_BUCKET", "raw")
MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
PROJECT_BUCKETS: tuple[str, ...] = ("raw", "clean", "abt")
EXPECTED_RAW_FILES: tuple[str, ...] = (
    "HomeCredit_columns_description.csv",
    "POS_CASH_balance.csv",
    "application_test.csv",
    "application_train.csv",
    "bureau.csv",
    "bureau_balance.csv",
    "credit_card_balance.csv",
    "installments_payments.csv",
    "previous_application.csv",
    "sample_submission.csv",
)


def get_minio_client():
    """Cria um cliente S3 configurado para o MinIO local."""
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT_URL,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_buckets(client) -> None:
    """Garante que os buckets padrao do projeto existem no MinIO."""
    existing = {bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])}
    for bucket in PROJECT_BUCKETS:
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)


def list_bucket_keys(client, bucket: str) -> set[str]:
    """Lista todas as chaves de objetos de um bucket, incluindo paginacao."""
    keys = set()
    continuation_token = None

    while True:
        kwargs = {"Bucket": bucket}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = client.list_objects_v2(**kwargs)
        keys.update(item["Key"] for item in response.get("Contents", []))

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")

    return keys


def find_downloaded_csvs(source_dir: Path) -> dict[str, Path]:
    """Mapeia os CSVs baixados por nome de arquivo."""
    return {csv_path.name: csv_path for csv_path in source_dir.rglob("*.csv")}


def upload_expected_csv_files(
    client,
    source_dir: Path,
    bucket: str,
    expected_files: tuple[str, ...],
) -> list[str]:
    """Envia os CSVs esperados para o bucket, substituindo objetos existentes."""
    csvs_by_name = find_downloaded_csvs(source_dir)
    downloaded_names = set(csvs_by_name)
    missing_from_download = sorted(
        file_name for file_name in expected_files if file_name not in downloaded_names
    )
    if missing_from_download:
        raise RuntimeError(
            "Kaggle download did not contain expected files: "
            + ", ".join(missing_from_download)
        )

    uploaded = []
    for key in expected_files:
        csv_path = csvs_by_name[key]
        client.upload_file(str(csv_path), bucket, key)
        uploaded.append(key)
    return uploaded


def missing_expected_files(client, bucket: str) -> list[str]:
    """Retorna os arquivos esperados que ainda nao existem no bucket."""
    existing = list_bucket_keys(client, bucket)
    return sorted(file_name for file_name in EXPECTED_RAW_FILES if file_name not in existing)


def replace_kaggle_raw_files() -> dict[str, object]:
    """Baixa a competicao Kaggle e substitui os CSVs esperados no bucket raw."""
    client = get_minio_client()
    ensure_buckets(client)

    with TemporaryDirectory() as tmpdir:
        download_dir = Path(tmpdir)
        source_path = Path(
            kagglehub.competition_download(COMPETITION_NAME, output_dir=str(download_dir))
        )
        replaced_files = upload_expected_csv_files(
            client,
            source_path,
            RAW_BUCKET,
            EXPECTED_RAW_FILES,
        )

    missing_files = missing_expected_files(client, RAW_BUCKET)
    if missing_files:
        raise RuntimeError(
            "Bucket raw is still missing expected files: " + ", ".join(missing_files)
        )

    return {
        "bucket": RAW_BUCKET,
        "replaced": replaced_files,
        "skipped": False,
        "missing_after_upload": [],
    }
