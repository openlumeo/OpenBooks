from types import SimpleNamespace

import pytest

from openbooks_server import retention


class Database:
    def __init__(self, keys=()):
        self.keys = keys
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        pass

    def execute(self, statement, params=()):
        self.calls.append((statement, params))
        return SimpleNamespace(fetchall=lambda: self.keys)


def test_cleanup_marks_only_successfully_deleted_objects(monkeypatch):
    connection = Database([("originals/expired",), ("originals/retry",)])
    deleted = []

    def delete_object(*, Bucket, Key):
        assert Bucket == "private-originals"
        if Key.endswith("retry"):
            raise RuntimeError("storage unavailable")
        deleted.append(Key)

    monkeypatch.setenv("OPENBOOKS_STORAGE_BUCKET", "private-originals")
    client = SimpleNamespace(
        delete_object=delete_object,
        get_paginator=lambda _operation: SimpleNamespace(paginate=lambda **_options: []),
    )
    monkeypatch.setattr(retention, "_services", lambda: (connection, client))
    with pytest.raises(RuntimeError, match="storage unavailable"):
        retention.delete_expired()

    assert "expires_at <= now()" in connection.calls[0][0]
    assert deleted == ["originals/expired"]
    assert len(connection.calls) == 2
    assert connection.calls[1][1] == ("originals/expired",)
