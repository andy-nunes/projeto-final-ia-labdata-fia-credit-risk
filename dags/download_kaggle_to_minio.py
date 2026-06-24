from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import os

import boto3
import kagglehub
from airflow.sdk import dag, task
from botocore.client import Config


COMPETITION_NAME = "home-credit-default-risk"
RAW_BUCKET = os.getenv("RAW_BUCKET", "raw")
MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
PROJECT_BUCKETS = ("raw", "clean", "abt")
EXPECTED_RAW_FILES = (
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
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT_URL,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_buckets(client) -> None:
    existing = {bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])}
    for bucket in PROJECT_BUCKETS:
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)


def list_bucket_keys(client, bucket: str) -> set[str]:
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
    return {csv_path.name: csv_path for csv_path in source_dir.rglob("*.csv")}


def upload_expected_csv_files(
    client,
    source_dir: Path,
    bucket: str,
    expected_files: tuple[str, ...],
) -> list[str]:
    csvs_by_name = find_downloaded_csvs(source_dir)
    missing_from_download = sorted(set(expected_files) - set(csvs_by_name))
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
    existing = list_bucket_keys(client, bucket)
    return sorted(set(EXPECTED_RAW_FILES) - existing)


@dag(
    dag_id="download_kaggle_to_minio",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["credit-risk", "kaggle", "minio"],
)
def download_kaggle_to_minio():
    @task
    def download_and_upload() -> dict[str, object]:
        client = get_minio_client()
        ensure_buckets(client)

        with TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            source_path = Path(
                kagglehub.competition_download(COMPETITION_NAME, output_dir=str(download_dir))
            )
            uploaded_files = upload_expected_csv_files(
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
            "replaced": uploaded_files,
            "skipped": False,
            "missing_after_upload": [],
        }

    download_and_upload()


download_kaggle_to_minio()
