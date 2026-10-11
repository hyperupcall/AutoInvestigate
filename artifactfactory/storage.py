import importlib
import os
from typing import List


class StorageBackend:
    def put_bytes(self, key: str, data: bytes) -> str:
        raise NotImplementedError

    def put_text(self, key: str, text: str) -> str:
        return self.put_bytes(key, text.encode("utf-8"))

    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def get_text(self, key: str) -> str:
        return self.get_bytes(key).decode("utf-8")

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def list(self, prefix: str = "") -> List[str]:
        raise NotImplementedError

    def uri(self, key: str) -> str:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key: str) -> str:
        key = key.replace("\\", "/").lstrip("/")
        path = os.path.abspath(os.path.join(self.root, key))
        if path != self.root and not path.startswith(self.root + os.sep):
            raise ValueError(f"path traversal detected for key: {key!r}")
        return path

    def put_bytes(self, key: str, data: bytes) -> str:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return self.uri(key)

    def get_bytes(self, key: str) -> bytes:
        with open(self._path(key), "rb") as f:
            return f.read()

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))

    def list(self, prefix: str = "") -> List[str]:
        base = self._path(prefix) if prefix else self.root
        if os.path.isfile(base):
            return [prefix]
        results: List[str] = []
        for dirpath, _dirs, filenames in os.walk(base):
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, self.root).replace(os.sep, "/")
                results.append(rel)
        return sorted(results)

    def uri(self, key: str) -> str:
        return "file://" + self._path(key)


class S3Storage(StorageBackend):
    def __init__(self, bucket: str, prefix: str = ""):
        try:
            boto3 = importlib.import_module("boto3")
        except ImportError as exc:
            raise RuntimeError(
                "S3Storage requires the 'boto3' package, which is not installed. "
                "Install it with `pip install boto3`, or use the local backend by "
                "setting AF_STORAGE=local."
            ) from exc
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = boto3.client("s3")

    def _key(self, key: str) -> str:
        key = key.lstrip("/")
        return f"{self.prefix}/{key}" if self.prefix else key

    def put_bytes(self, key: str, data: bytes) -> str:
        self._client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)
        return self.uri(key)

    def get_bytes(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self.bucket, Key=self._key(key))
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except Exception:
            return False

    def list(self, prefix: str = "") -> List[str]:
        full = self._key(prefix) if prefix else self.prefix
        resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=full)
        out: List[str] = []
        for obj in resp.get("Contents", []):
            k = obj["Key"]
            if self.prefix and k.startswith(self.prefix + "/"):
                k = k[len(self.prefix) + 1:]
            out.append(k)
        return sorted(out)

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{self._key(key)}"


def build_storage(config) -> StorageBackend:
    if config.storage_backend == "s3":
        return S3Storage(config.s3_bucket, config.s3_prefix)
    return LocalStorage(os.path.join(config.data_dir, "artifacts"))
