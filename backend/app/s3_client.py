import boto3
from botocore.exceptions import ClientError
from .config import get_settings


def get_s3_client():
    settings = get_settings()
    if not settings.s3_access_key or not settings.s3_secret_key:
        raise ValueError("S3 credentials not configured")
    
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def generate_presigned_upload(filename: str, content_type: str, size: int) -> dict:
    """Generate presigned URL for multipart upload to SOS"""
    settings = get_settings()
    s3_client = get_s3_client()
    
    key = f"uploads/{filename}"
    
    try:
        response = s3_client.generate_presigned_post(
            Bucket=settings.s3_bucket_originals,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, size + 1024],  # Allow small buffer
            ],
            ExpiresIn=3600,  # 1 hour
        )
        return {
            "upload_id": key,
            "upload_url": response["url"],
            "fields": response["fields"],
        }
    except ClientError as e:
        raise ValueError(f"Failed to generate presigned URL: {e}")
