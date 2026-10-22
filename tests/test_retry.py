import pytest

from triage.providers.base import FatalProviderError, TransientProviderError
from triage.providers.retry import call_with_backoff


def _scripted(values):
    it = iter(values)

    def fn():
        v = next(it)
        if isinstance(v, Exception):
            raise v
        return v

    return fn


def test_backoff_retries_transient_then_succeeds():
    slept = []
    fn = _scripted([TransientProviderError("429"), TransientProviderError("503"), "ok"])
    assert call_with_backoff(fn, max_attempts=3, base_delay_s=0.01, sleep=slept.append) == "ok"
    assert len(slept) == 2 and slept[1] >= slept[0] * 1.0


def test_backoff_does_not_retry_fatal():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise FatalProviderError("401")

    with pytest.raises(FatalProviderError):
        call_with_backoff(fn, 3, sleep=lambda s: None)
    assert calls["n"] == 1


def test_backoff_gives_up_after_max_attempts():
    fn = _scripted([TransientProviderError(str(i)) for i in range(3)])
    with pytest.raises(TransientProviderError, match="2"):
        call_with_backoff(fn, max_attempts=3, sleep=lambda s: None)
