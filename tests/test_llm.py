import pytest

from app.config import Settings
from app.llm import GeminiClient, OpenAIClient, build_llm

def make(**kw):
    values = {"gemini_api_key": "", "openai_api_key": "", **kw}
    return Settings(_env_file=None, **values)


def test_gemini_is_the_default_provider():
    client = build_llm(make(gemini_api_key="k"))
    assert isinstance(client, GeminiClient)


def test_openai_provider_can_be_selected():
    assert isinstance(build_llm(make(llm_provider="openai", openai_api_key="k")), OpenAIClient)


def test_missing_key_fails_fast_at_startup():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        build_llm(make())
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_llm(make(llm_provider="openai"))


def test_unknown_provider_is_rejected():
    with pytest.raises(RuntimeError, match="Unknown LLM_PROVIDER"):
        build_llm(make(llm_provider="skynet"))