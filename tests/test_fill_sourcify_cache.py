import builtins

import pytest

from ethcode.tools.addresses import read_addresses
from ethcode.tools.fill_sourcify_cache import _duckdb, _settings


def test_read_addresses_validates_normalizes_and_deduplicates(tmp_path):
    address = "0x" + "AB" * 20
    source = tmp_path / "addresses.csv"
    source.write_text(
        f"\ufeffchain,address\n1,{address}\n1,{address.lower()}\n5,{'0x' + '12' * 20}\n",
        encoding="utf-8",
    )

    locations = read_addresses(source)

    assert [(item.chain_id, item.address) for item in locations] == [
        (1, address.lower()),
        (5, "0x" + "12" * 20),
    ]


def test_settings_accepts_objects_and_json_objects():
    assert _settings(None) == {}
    assert _settings({"optimizer": {"enabled": True}}) == {
        "optimizer": {"enabled": True}}
    assert _settings('{"evmVersion":"paris"}') == {"evmVersion": "paris"}
    with pytest.raises(ValueError, match="invalid compiler settings"):
        _settings("[]")


def test_missing_duckdb_explains_optional_extra(monkeypatch):
    real_import = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == "duckdb":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    with pytest.raises(RuntimeError, match=r"ethcode\[dataset\]"):
        _duckdb()
