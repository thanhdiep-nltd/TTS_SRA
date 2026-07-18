"""Đọc/ghi object trên MinIO/S3 qua S3Hook (Connection `aws_minio`).

Truyền S3 key giữa các task (không truyền nội dung lớn qua XCom).
"""

_CONN_ID = "aws_minio"


def _hook():
    """Khởi tạo S3Hook lười (import trong hàm để test offline không cần Airflow)."""
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    return S3Hook(aws_conn_id=_CONN_ID)


def get_bytes(bucket: str, key: str) -> bytes:
    """Tải object dạng bytes."""
    obj = _hook().get_key(key=key, bucket_name=bucket)
    return obj.get()["Body"].read()


def get_text(bucket: str, key: str) -> str:
    """Tải object dạng text UTF-8."""
    return get_bytes(bucket, key).decode("utf-8")


def put_text(bucket: str, key: str, data: str) -> str:
    """Ghi (đè) text lên S3; trả về key đã ghi."""
    _hook().load_string(string_data=data, key=key, bucket_name=bucket, replace=True)
    return key


def exists(bucket: str, key: str) -> bool:
    return _hook().check_for_key(key=key, bucket_name=bucket)


def delete_prefix(bucket: str, prefix: str) -> int:
    """Xóa mọi object dưới một prefix (dọn file tạm). Trả về số object đã xóa."""
    hook = _hook()
    keys = hook.list_keys(bucket_name=bucket, prefix=prefix) or []
    if keys:
        hook.delete_objects(bucket=bucket, keys=keys)
    return len(keys)
