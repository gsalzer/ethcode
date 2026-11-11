from pathlib import Path

from ethcode.providers import EtherscanProvider, SourcifyProvider


def test_provider_cache_defaults_are_under_user_cache():
    root = Path.home() / ".cache" / "ethcode"
    assert EtherscanProvider().cache.root == root / "etherscan"
    assert SourcifyProvider().cache.root == root / "sourcify"

