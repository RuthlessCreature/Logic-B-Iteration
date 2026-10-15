from pathlib import Path

import pytest

from logic_b.store import LocalStore, R2Store, StoreNotConnected


def test_local_store_is_atomic_measurable_and_blocks_traversal(tmp_path):
    store = LocalStore(tmp_path / "cache")
    store.put_bytes("events/2025-01.json", b"abc")
    assert store.get_bytes("events/2025-01.json") == b"abc"
    assert store.actual_bytes() == 3
    with pytest.raises(ValueError, match="safe relative"):
        store.put_bytes("../outside", b"no")


def test_r2_is_unavailable_without_explicit_client():
    store = R2Store("", None)
    with pytest.raises(StoreNotConnected):
        store.actual_bytes()


class FakeR2:
    def __init__(self):
        self.data = {}
        self.calls = 0

    def put_object(self, *, Bucket, Key, Body):
        self.data[(Bucket, Key)] = Body

    def get_object(self, *, Bucket, Key):
        from io import BytesIO
        return {"Body": BytesIO(self.data[(Bucket, Key)])}

    def list_objects_v2(self, *, Bucket, Prefix, **kwargs):
        rows = [{"Size": len(body)} for (bucket, key), body in self.data.items()
                if bucket == Bucket and key.startswith(Prefix)]
        self.calls += 1
        if self.calls == 1 and len(rows) > 1:
            return {"Contents": rows[:1], "IsTruncated": True, "NextContinuationToken": "page2"}
        return {"Contents": rows[1:] if self.calls > 1 else rows, "IsTruncated": False}


def test_r2_adapter_uses_object_metadata_and_paginates():
    client = FakeR2()
    store = R2Store("market", client, "goal")
    store.put_bytes("2025/a", b"123")
    store.put_bytes("2025/b", b"12345")
    assert store.get_bytes("2025/a") == b"123"
    assert store.actual_bytes() == 8
