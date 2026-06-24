from pathlib import Path
import os

import boto3
import streamlit as st
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError


DATA_DIR = Path(os.getenv("DATA_DIR", "/app/Dados"))
MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
PROJECT_BUCKETS = ("raw", "clean", "abt")


def list_data_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    return sorted(path for path in DATA_DIR.rglob("*") if path.is_file())


def get_minio_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT_URL,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def list_minio_buckets() -> tuple[bool, str, list[str]]:
    client = get_minio_client()
    try:
        ensure_project_buckets(client)
        response = client.list_buckets()
    except (BotoCoreError, ClientError) as exc:
        return False, str(exc), []
    return True, "Conexao com MinIO ativa.", [bucket["Name"] for bucket in response.get("Buckets", [])]


def ensure_project_buckets(client) -> None:
    existing = {bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])}
    for bucket in PROJECT_BUCKETS:
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)


def list_bucket_objects(bucket: str) -> list[dict[str, object]]:
    client = get_minio_client()
    response = client.list_objects_v2(Bucket=bucket)
    return [
        {"objeto": item["Key"], "tamanho_bytes": item["Size"]}
        for item in response.get("Contents", [])
    ]


def check_minio() -> tuple[bool, str]:
    client = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT_URL,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    try:
        client.list_buckets()
    except (BotoCoreError, ClientError) as exc:
        return False, str(exc)
    return True, "Conexao com MinIO ativa."


st.set_page_config(page_title="Credit Risk - FIA", layout="wide")
st.title("Credit Risk - FIA")
st.caption("Ambiente local conectado a Dados, MinIO e Streamlit.")

files = list_data_files()
st.subheader("Volume Dados")
st.write(f"Diretorio montado: `{DATA_DIR}`")
st.write(f"Arquivos encontrados: `{len(files)}`")

if files:
    st.dataframe(
        [{"arquivo": str(path.relative_to(DATA_DIR)), "tamanho_bytes": path.stat().st_size} for path in files],
        use_container_width=True,
    )

st.subheader("MinIO")
ok, message, buckets = list_minio_buckets()
if ok:
    st.success(message)
    st.write(f"Buckets do projeto: `{', '.join(PROJECT_BUCKETS)}`")
    st.write(f"Buckets encontrados: `{len(buckets)}`")
    if buckets:
        selected_bucket = st.selectbox("Bucket", buckets)
        st.dataframe(list_bucket_objects(selected_bucket), use_container_width=True)
else:
    st.error(message)
