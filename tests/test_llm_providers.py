"""Text provider selection and credential/model handling. Fake SDK clients only: no network, no paid calls."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("openai")

from generation import api_clients  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class FakeSDK:
    """Stands in for groq.Groq / openai.OpenAI: records constructor kwargs and chat calls."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        FakeSDK.instances.append(self)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fake text"))])


@pytest.fixture
def sdk(monkeypatch):
    FakeSDK.instances = []
    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=FakeSDK))
    monkeypatch.setattr(api_clients, "OpenAI", FakeSDK)
    monkeypatch.setattr(api_clients, "get_config", lambda: SimpleNamespace(
        groq_api_key="groq-key", default_llm_model="llama-3.3-70b-versatile",
        google_api_key="google-key", gemini_model="gemini-x",
    ))
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "DEFAULT_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    return FakeSDK


def test_groq_client_uses_groq_key_endpoint_and_model(sdk, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")  # must be ignored by Groq
    client = api_clients.GroqClient()
    assert sdk.instances[-1].kwargs == {"api_key": "groq-key"}  # Groq SDK default endpoint, no base_url
    assert client.model == "llama-3.3-70b-versatile"
    assert client.generate_text("hi") == "fake text"
    assert sdk.instances[-1].calls[0]["model"] == "llama-3.3-70b-versatile"


def test_groq_client_without_groq_key_fails_even_with_openrouter_key(sdk, monkeypatch):
    monkeypatch.setattr(api_clients, "get_config", lambda: SimpleNamespace(groq_api_key="", default_llm_model="m"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    with pytest.raises(ValueError, match="Groq API key"):
        api_clients.GroqClient()


def test_openrouter_client_reads_openrouter_key_and_model(sdk, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "x-ai/grok-test")
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "llama-3.3-70b-versatile")  # must not win
    client = api_clients.OpenRouterTextClient()
    assert sdk.instances[-1].kwargs == {"api_key": "or-key", "base_url": "https://openrouter.ai/api/v1"}
    assert client.generate_text("hi", max_tokens=5) == "fake text"
    assert sdk.instances[-1].calls[0]["model"] == "x-ai/grok-test"


def test_openrouter_client_never_falls_back_to_groq_model_or_key(sdk, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    with pytest.raises(ValueError, match="OPENROUTER_MODEL"):
        api_clients.OpenRouterTextClient()
    monkeypatch.delenv("OPENROUTER_API_KEY")
    monkeypatch.setenv("OPENROUTER_MODEL", "x-ai/grok-test")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        api_clients.OpenRouterTextClient()


def test_explicit_arguments_override_environment(sdk, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "env-model")
    client = api_clients.OpenRouterTextClient(api_key="arg-key", model="arg-model")
    assert (client.api_key, client.model) == ("arg-key", "arg-model")


@pytest.mark.parametrize("provider, expected", [
    ("groq", "GroqClient"), ("GROQ", "GroqClient"),
    ("openrouter", "OpenRouterTextClient"), ("gemini", "GeminiClient"),
])
def test_make_llm_client_selects_provider(sdk, monkeypatch, provider, expected):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "x-ai/grok-test")
    assert type(api_clients.make_llm_client(provider)).__name__ == expected


def test_make_llm_client_rejects_unknown_provider(sdk):
    with pytest.raises(ValueError, match="Unknown LLM provider: nope"):
        api_clients.make_llm_client("nope")


def test_book_example_does_not_import_the_celery_worker(monkeypatch):
    for name in [m for m in sys.modules if m == "worker" or m.startswith("worker.")]:
        monkeypatch.delitem(sys.modules, name)
    spec = importlib.util.spec_from_file_location("book_example", ROOT / "examples" / "book_example.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "worker.tasks" not in sys.modules
    assert module.generate_book_comic.__module__ == "book_comic.pipeline"


def test_worker_generate_comic_selects_openrouter_text(monkeypatch, tmp_path):
    pytest.importorskip("celery")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("CHROMADB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "x-ai/grok-test")
    monkeypatch.delenv("DEFAULT_LLM_MODEL", raising=False)
    seen = {}

    class FakeCrafter:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def generate_comic(self, **kwargs):
            return []

    monkeypatch.setitem(sys.modules, "core", SimpleNamespace(ComicCrafter=FakeCrafter))
    from worker import tasks

    tasks.generate_comic("story")
    assert seen["llm_provider"] == "openrouter"
    assert "DEFAULT_LLM_MODEL" not in tasks.os.environ
