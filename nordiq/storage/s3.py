"""S3 storage helpers for report files."""
from __future__ import annotations
import io
from nordiq.core.config import get_settings

def _client():
    import boto3
    s = get_settings()
    kwargs = {"region_name": s.aws_region}
    if s.aws_access_key_id:
        kwargs["aws_access_key_id"] = s.aws_access_key_id
        kwargs["aws_secret_access_key"] = s.aws_secret_access_key
    return boto3.client("s3", **kwargs)

def upload_file(local_path: str, s3_key: str) -> str:
    """Upload local file to S3; return S3 URI (s3://bucket/key)."""
    s = get_settings()
    _client().upload_file(local_path, s.s3_bucket, s3_key)
    return f"s3://{s.s3_bucket}/{s3_key}"

def download_fileobj(s3_uri: str) -> tuple[io.BytesIO, str]:
    """Download S3 object; return (BytesIO, filename)."""
    s = get_settings()
    # s3_uri = s3://bucket/key
    key = s3_uri.removeprefix(f"s3://{s.s3_bucket}/")
    buf = io.BytesIO()
    _client().download_fileobj(s.s3_bucket, key, buf)
    buf.seek(0)
    filename = key.split("/")[-1]
    return buf, filename

def presigned_url(s3_uri: str, expires_in: int = 3600) -> str:
    """Generate a presigned GET URL for the S3 object."""
    s = get_settings()
    key = s3_uri.removeprefix(f"s3://{s.s3_bucket}/")
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )
