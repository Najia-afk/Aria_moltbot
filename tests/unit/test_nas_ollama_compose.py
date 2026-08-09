from pathlib import Path

import yaml


COMPOSE_FILE = Path(__file__).parents[2] / "deploy" / "nas-ollama" / "compose.yml"


def test_nas_ollama_is_lan_exposed_and_hardened():
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    service = compose["services"]["ollama"]

    assert service["image"] == (
        "ollama/ollama:0.32.6@"
        "sha256:b88c73ace3e115f8ec53dc8761ae1c0aabfa675406e3681786b98757ce050f42"
    )
    assert service["pull_policy"] == "missing"
    assert service["ports"] == [
        {
            "name": "ollama-lan",
            "target": 11434,
            "published": "11434",
            "protocol": "tcp",
        }
    ]
    assert service["environment"]["OLLAMA_NO_CLOUD"] == "1"
    assert service["environment"]["OLLAMA_CONTEXT_LENGTH"] == "131072"
    assert service["environment"]["OLLAMA_FLASH_ATTENTION"] == "1"
    assert service["environment"]["OLLAMA_KV_CACHE_TYPE"] == "q8_0"
    assert service["environment"]["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert service["environment"]["OLLAMA_MAX_QUEUE"] == "8"
    assert service["environment"]["OLLAMA_NUM_PARALLEL"] == "1"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges=true" in service["security_opt"]
    assert service["mem_limit"] == "56g"


def test_model_init_pulls_on_nas_not_on_mac():
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    init = compose["services"]["model-init"]

    assert init["image"] == compose["services"]["ollama"]["image"]
    assert init["restart"] == "no"
    assert init["environment"]["OLLAMA_HOST"] == "http://ollama:11434"
    assert "ports" not in init
    assert init["depends_on"]["ollama"]["condition"] == "service_healthy"
