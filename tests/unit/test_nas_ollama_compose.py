from pathlib import Path

import yaml


COMPOSE_FILE = Path(__file__).parents[2] / "deploy" / "nas-ollama" / "compose.yml"


def test_nas_ollama_is_loopback_only_and_hardened():
    service = yaml.safe_load(COMPOSE_FILE.read_text())["services"]["ollama"]

    assert service["image"] == (
        "ollama/ollama:0.32.6@"
        "sha256:b88c73ace3e115f8ec53dc8761ae1c0aabfa675406e3681786b98757ce050f42"
    )
    assert service["ports"] == [
        {
            "name": "ollama-loopback",
            "target": 11434,
            "published": "11434",
            "host_ip": "127.0.0.1",
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
