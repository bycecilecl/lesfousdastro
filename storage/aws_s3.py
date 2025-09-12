# storage/aws_s3.py
import boto3
import os
from datetime import timedelta

S3_BUCKET = os.getenv("AWS_S3_BUCKET")                 # ex: lesfousdastro-pdf
S3_REGION = os.getenv("AWS_REGION", "eu-west-3")       # adapte si besoin

def s3_key_for_point_astral(date_parts, filename):
    # date_parts = ("2025","09","10") / filename = "xxxx.pdf"
    yyyy, mm, dd = date_parts
    return f"point_astral/{yyyy}/{mm}/{dd}/{filename}"

def upload_file_and_presign(local_path, key_prefix="point_astral", content_type="application/pdf", expires_seconds=7*24*3600):
    bucket = os.getenv("AWS_S3_BUCKET")
    region = os.getenv("AWS_REGION", "eu-west-3")
    key = f"{key_prefix}/{os.path.basename(local_path)}"

    s3 = boto3.client("s3", region_name=region)
    s3.upload_file(local_path, bucket, key, ExtraArgs={"ContentType": content_type})
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )
    return {"bucket": bucket, "key": key, "url": url}