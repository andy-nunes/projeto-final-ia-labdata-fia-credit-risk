"""Inicializa os buckets MinIO necessarios antes de subir o Streamlit."""

import os
import time

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from scripts.integrations_config import get_integrations_config


MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")


def _get_minio_settings() -> tuple[str, tuple[str, ...]]:
    """Resolve endpoint e buckets via loader central de integrações."""
    minio_config = get_integrations_config().minio
    return minio_config.endpoint_url, tuple(minio_config.project_buckets)


def get_minio_client():
    """Cria um cliente S3 apontando para o MinIO local."""
    endpoint_url, _ = _get_minio_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def wait_for_minio():
    """Aguarda o MinIO ficar disponivel e retorna um cliente conectado."""
    endpoint_url, _ = _get_minio_settings()
    client = get_minio_client()
    for _ in range(30):
        try:
            client.list_buckets()
            return client
        except EndpointConnectionError:
            time.sleep(2)
    raise RuntimeError(f"MinIO is not reachable at {endpoint_url}")


def ensure_buckets(client) -> None:
    """Cria os buckets do projeto quando ainda nao existem."""
    _, project_buckets = _get_minio_settings()
    existing = {bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])}
    for bucket in project_buckets:
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
            print(f"Created bucket: {bucket}")
        else:
            print(f"Bucket already exists: {bucket}")


try:
    ensure_buckets(wait_for_minio())
except (BotoCoreError, ClientError) as exc:
    raise RuntimeError("Failed to initialize MinIO buckets") from exc
