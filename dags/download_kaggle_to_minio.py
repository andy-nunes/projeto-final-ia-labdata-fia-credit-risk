from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import os

import boto3
import kagglehub
from airflow.decorators import dag, task
from botocore.client import Config
from botocore.exceptions import ClientError


COMPETITION_NAME = "home-credit-default-risk"
LOCAL_RAW_DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/Dados")) / "raw"
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


def object_exists(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    return True


def upload_csv_files(client, source_dir: Path, bucket: str) -> list[str]:
    uploaded = []
    for csv_path in sorted(source_dir.glob("*.csv")):
        key = csv_path.name
        if object_exists(client, bucket, key):
            continue
        client.upload_file(str(csv_path), bucket, key)
        uploaded.append(key)
    return uploaded


def bucket_has_expected_files(client, bucket: str) -> bool:
    response = client.list_objects_v2(Bucket=bucket)
    existing = {item["Key"] for item in response.get("Contents", [])}
    return set(EXPECTED_RAW_FILES).issubset(existing)


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

        if bucket_has_expected_files(client, RAW_BUCKET):
            return {
                "bucket": RAW_BUCKET,
                "uploaded": [],
                "skipped": True,
                "reason": "Bucket already contains expected Kaggle CSV files.",
            }

        if any(LOCAL_RAW_DATA_DIR.glob("*.csv")):
            uploaded_files = upload_csv_files(client, LOCAL_RAW_DATA_DIR, RAW_BUCKET)
        else:
            with TemporaryDirectory() as tmpdir:
                download_dir = Path(tmpdir)
                source_path = Path(
                    kagglehub.competition_download(COMPETITION_NAME, output_dir=str(download_dir))
                )
                uploaded_files = upload_csv_files(client, source_path, RAW_BUCKET)

        return {"bucket": RAW_BUCKET, "uploaded": uploaded_files, "skipped": False}

    download_and_upload()


download_kaggle_to_minio()
