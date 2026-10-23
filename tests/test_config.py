import pytest

from triage.config import ConfigError, load_settings

ENV_VARS = [
    "LLM_PROVIDER", "TEMPERATURE", "CACHE_ENABLED", "MAX_TOKENS",
    "EVAL_MAX_COST_USD", "MODERATION_ENABLED",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults():
    s = load_settings(env_file=None)
    assert s.llm_provider == "anthropic" and s.eval_max_cost_usd == 2.0 and s.moderation_enabled is True


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("TEMPERATURE", "0.2")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    s = load_settings(env_file=None)
    assert s.temperature == 0.2 and s.cache_enabled is False


def test_invalid_number_raises_config_error(monkeypatch):
    monkeypatch.setenv("MAX_TOKENS", "mucho")
    with pytest.raises(ConfigError):
        load_settings(env_file=None)


def test_default_prompt_is_v3_chosen_by_evals(monkeypatch):
    monkeypatch.delenv("PROMPT_VERSION", raising=False)
    assert load_settings(env_file=None).prompt_version == "v3"
