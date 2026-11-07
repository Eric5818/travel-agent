import pytest

from app.config import ConfigError, load


def test_load_raises_when_deepseek_key_missing():
    with pytest.raises(ConfigError):
        load(env={})


def test_missing_tavily_key_marks_degraded():
    settings = load(env={"DEEPSEEK_API_KEY": "sk-test"})

    assert settings.tavily_configured is False
    assert settings.degraded is True


def test_tavily_configured_when_key_present():
    settings = load(
        env={"DEEPSEEK_API_KEY": "sk-test", "TAVILY_API_KEY": "tvly-test"}
    )

    assert settings.tavily_configured is True
    assert settings.degraded is False


def test_defaults_are_applied():
    settings = load(env={"DEEPSEEK_API_KEY": "sk-test"})

    assert settings.deepseek_base_url == "https://api.deepseek.com/v1"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.weather_base_url == "https://wttr.in"


def test_repr_does_not_leak_keys():
    settings = load(
        env={
            "DEEPSEEK_API_KEY": "sk-super-secret",
            "TAVILY_API_KEY": "tvly-super-secret",
        }
    )

    rendered = repr(settings) + str(settings)

    assert "sk-super-secret" not in rendered
    assert "tvly-super-secret" not in rendered
