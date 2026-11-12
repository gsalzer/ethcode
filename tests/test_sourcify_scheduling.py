import json
import time
from unittest.mock import patch

import pytest

from ethcode.errors import ProviderUnavailableError
from ethcode.providers import SourcifyProvider


def assert_scheduling(error, *, retryable, condition):
    assert error.provider == "sourcify"
    assert error.category == "request_scheduling"
    assert error.origin == "cache"
    assert error.retryable is retryable
    assert error.details["condition"] == condition


def test_corrupt_and_invalid_cooldown_are_structured(tmp_path):
    provider = SourcifyProvider(tmp_path, email="test@example.org")
    provider._cooldown_path.write_text("not-json")
    with pytest.raises(ProviderUnavailableError) as raised:
        provider._wait_for_cooldown()
    assert_scheduling(raised.value, retryable=False, condition="corrupt")

    provider._cooldown_path.write_text(json.dumps({"retry_at": True}))
    with pytest.raises(ProviderUnavailableError) as raised:
        provider._wait_for_cooldown()
    assert_scheduling(raised.value, retryable=False, condition="invalid_timestamp")


def test_unreadable_cooldown_is_retryable_scheduling_failure(tmp_path):
    provider = SourcifyProvider(tmp_path, email="test@example.org")
    provider._cooldown_path.write_text("{}")
    with patch("pathlib.Path.read_text", side_effect=OSError("unreadable")):
        with pytest.raises(ProviderUnavailableError) as raised:
            provider._wait_for_cooldown()
    assert_scheduling(raised.value, retryable=True, condition="unreadable")


def test_excessive_valid_cooldown_is_retryable(tmp_path):
    provider = SourcifyProvider(
        tmp_path, email="test@example.org", max_wait=1)
    provider._cooldown_path.write_text(json.dumps({"retry_at": time.time() + 60}))
    with pytest.raises(ProviderUnavailableError) as raised:
        provider._wait_for_cooldown()
    assert_scheduling(
        raised.value, retryable=True, condition="wait_exceeds_maximum")


def test_request_lock_failure_is_structured(tmp_path):
    root = tmp_path / "cache"
    root.write_text("not a directory")
    provider = SourcifyProvider(root, email="test@example.org")
    with pytest.raises(ProviderUnavailableError) as raised:
        with provider._request_lock():
            pass
    error = raised.value
    assert error.provider == "sourcify"
    assert error.category == "request_scheduling"
    assert error.origin == "cache"
    assert error.retryable
    assert error.details["component"] == "request_lock"
