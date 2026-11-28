"""Private original storage and expiry. Run this module periodically to delete expired originals."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4


def _services():
    import boto3
    import psycopg
    from botocore.config import Config

    client = boto3.client(
        "s3", endpoint_url=os.environ["OPENBOOKS_STORAGE_ENDPOINT"],
        config=Config(s3={"addressing_style": "path"}),
    )
    return psycopg.connect(os.environ["OPENBOOKS_RETENTION_DATABASE_URL"], autocommit=True), client


def store_original(path: Path, name: str, size: int, owner: str) -> None:
    from boto3.s3.transfer import TransferConfig

    bucket = os.environ["OPENBOOKS_STORAGE_BUCKET"]
    key = f"originals/{uuid4().hex}"
    connection, client = _services()
    with connection:
        connection.execute(
            "insert into retained_originals (object_key, owner_id, file_name, byte_size) values (%s,%s,%s,%s)",
            (key, owner, name, size),
        )
        try:
            client.upload_file(str(path), bucket, key, Config=TransferConfig(use_threads=False))
        except Exception:
            # The pending row also lets the expiry job retry this deletion if storage is unreachable.
            connection.execute("update retained_originals set expires_at = now() where object_key = %s", (key,))
            raise
        connection.execute("update retained_originals set stored_at = now() where object_key = %s", (key,))


def delete_expired() -> int:
    bucket = os.environ["OPENBOOKS_STORAGE_BUCKET"]
    connection, client = _services()
    deleted = 0
    with connection:
        rows = connection.execute(
            "select object_key from retained_originals where deleted_at is null and expires_at <= now() "
            "order by expires_at, object_key limit 250"
        ).fetchall()
        for (key,) in rows:
            pages = client.get_paginator("list_multipart_uploads").paginate(Bucket=bucket, Prefix=key)
            for page in pages:
                for upload in page.get("Uploads", ()):
                    if upload["Key"] == key:
                        client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload["UploadId"])
            client.delete_object(Bucket=bucket, Key=key)
            connection.execute("update retained_originals set deleted_at = now() where object_key = %s", (key,))
            deleted += 1
    return deleted


if __name__ == "__main__":
    print(f"Expired originals deleted: {delete_expired()}")
