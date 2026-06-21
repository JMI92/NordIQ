"""S3 storage helpers for report files and customer document archives."""
from __future__ import annotations

import io
from uusio.core.config import get_settings


def _client():
    import boto3
    s = get_settings()
    kwargs = {"region_name": s.aws_region}
    if s.aws_access_key_id:
        kwargs["aws_access_key_id"] = s.aws_access_key_id
        kwargs["aws_secret_access_key"] = s.aws_secret_access_key
    return boto3.client("s3", **kwargs)


def _bucket() -> str:
    return get_settings().s3_bucket


def customer_prefix(customer_id: str, folder: str = "") -> str:
    """Return S3 key prefix for a customer's folder.

    folder: contracts | reports | invoices | audits (empty = root)
    """
    base = f"customers/{customer_id}"
    return f"{base}/{folder}/" if folder else f"{base}/"


def upload_file(local_path: str, s3_key: str) -> str:
    """Upload a local file to S3; return S3 URI."""
    _client().upload_file(local_path, _bucket(), s3_key)
    return f"s3://{_bucket()}/{s3_key}"


def upload_bytes(data: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes to S3; return S3 URI."""
    _client().put_object(Bucket=_bucket(), Key=s3_key, Body=data, ContentType=content_type)
    return f"s3://{_bucket()}/{s3_key}"


def download_fileobj(s3_uri: str) -> tuple[io.BytesIO, str]:
    """Download S3 object; return (BytesIO, filename)."""
    key = _uri_to_key(s3_uri)
    buf = io.BytesIO()
    _client().download_fileobj(_bucket(), key, buf)
    buf.seek(0)
    return buf, key.split("/")[-1]


def presigned_url(s3_uri: str, expires_in: int = 3600) -> str:
    """Generate a presigned GET URL valid for expires_in seconds."""
    key = _uri_to_key(s3_uri)
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=expires_in,
    )


def list_objects(prefix: str) -> list[dict]:
    """List objects under prefix; return list of {key, size, last_modified}."""
    paginator = _client().get_paginator("list_objects_v2")
    result = []
    for page in paginator.paginate(Bucket=_bucket(), Prefix=prefix):
        for obj in page.get("Contents", []):
            result.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
                "filename": obj["Key"].split("/")[-1],
                "s3_uri": f"s3://{_bucket()}/{obj['Key']}",
            })
    return result


def delete_object(s3_uri: str) -> None:
    key = _uri_to_key(s3_uri)
    _client().delete_object(Bucket=_bucket(), Key=key)


def _uri_to_key(s3_uri: str) -> str:
    return s3_uri.removeprefix(f"s3://{_bucket()}/")
