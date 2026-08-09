import os

from aria_engine.llm_gateway import LLMGateway


def _gateway():
    return LLMGateway.__new__(LLMGateway)


def test_resolve_model_expands_os_environ_api_base(monkeypatch):
    monkeypatch.setenv("NAS_OLLAMA_URL", "http://nas.example.internal:11434")
    gateway = _gateway()
    gateway._models_config = {
        "models": {
            "nas_ollama": {
                "litellm": {
                    "model": "ollama_chat/aria-primary",
                    "api_base": "os.environ/NAS_OLLAMA_URL",
                }
            }
        }
    }

    model, extra = gateway._resolve_model("nas_ollama")

    assert model == "ollama_chat/aria-primary"
    assert extra["api_base"] == "http://nas.example.internal:11434"


def test_resolve_model_skips_unset_env_var(monkeypatch):
    monkeypatch.delenv("NAS_OLLAMA_URL", raising=False)
    gateway = _gateway()
    gateway._models_config = {
        "models": {
            "nas_ollama": {
                "litellm": {
                    "model": "ollama_chat/aria-primary",
                    "api_base": "os.environ/NAS_OLLAMA_URL",
                }
            }
        }
    }

    _, extra = gateway._resolve_model("nas_ollama")

    assert "api_base" not in extra


def test_resolve_model_passes_through_literal_api_base():
    gateway = _gateway()
    gateway._models_config = {
        "models": {
            "mlx": {
                "litellm": {
                    "model": "openai/mlx-community/Qwen3.5-4B-MLX-4bit",
                    "api_base": "http://host.docker.internal:8080/v1",
                }
            }
        }
    }

    _, extra = gateway._resolve_model("mlx")

    assert extra["api_base"] == "http://host.docker.internal:8080/v1"
