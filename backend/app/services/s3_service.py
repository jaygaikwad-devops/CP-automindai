"""S3 service for file uploads using aioboto3."""

import aioboto3

from app.core.config import settings


async def upload_file(bucket: str, key: str, file_data: bytes, content_type: str) -> None:
    """Upload a file to S3.

    Args:
        bucket: S3 bucket name.
        key: S3 object key (path).
        file_data: Raw bytes of the file.
        content_type: MIME type of the file.
    """
    session = aioboto3.Session(
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        region_name=settings.aws_region,
    )
    async with session.client("s3") as s3_client:
        await s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_data,
            ContentType=content_type,
        )
