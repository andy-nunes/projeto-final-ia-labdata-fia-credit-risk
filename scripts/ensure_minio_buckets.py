"""Inicializa os buckets MinIO necessarios antes de subir o Streamlit."""

import os
import time

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError


MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
PROJECT_BUCKETS = ("raw", "clean", "abt")


def get_minio_client():
    """Cria um cliente S3 apontando para o MinIO local."""
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT_URL,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def wait_for_minio():
    """Aguarda o MinIO ficar disponivel e retorna um cliente conectado."""
    client = get_minio_client()
    for _ in range(30):
        try:
            client.list_buckets()
            return client
        except EndpointConnectionError:
            time.sleep(2)
    raise RuntimeError(f"MinIO is not reachable at {MINIO_ENDPOINT_URL}")


def ensure_buckets(client) -> None:
    """Cria os buckets do projeto quando ainda nao existem."""
    existing = {bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])}
    for bucket in PROJECT_BUCKETS:
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
            print(f"Created bucket: {bucket}")
        else:
            print(f"Bucket already exists: {bucket}")


try:
    ensure_buckets(wait_for_minio())
except (BotoCoreError, ClientError) as exc:
    raise RuntimeError("Failed to initialize MinIO buckets") from exc
