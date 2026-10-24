import dataclasses

import pytest

from triage.config import ConfigError
from triage.providers import get_provider, model_for


def test_gemini_requires_key(settings_tmp):
    s = dataclasses.replace(settings_tmp, gemini_api_key=None)
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        get_provider("gemini", s)


def test_gemini_provider_built_with_key(settings_tmp):
    s = dataclasses.replace(settings_tmp, gemini_api_key="k")
    assert get_provider("gemini", s).name == "gemini"


def test_model_for_each_provider(settings_tmp):
    assert model_for("anthropic", settings_tmp) == settings_tmp.anthropic_model
    assert model_for("gemini", settings_tmp) == settings_tmp.gemini_model


def test_unknown_provider(settings_tmp):
    with pytest.raises(ConfigError, match="openai"):
        get_provider("openai", settings_tmp)
