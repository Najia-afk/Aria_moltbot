from pathlib import Path

import yaml


COMPOSE_FILE = Path(__file__).parents[2] / "deploy" / "nas-ollama" / "compose.yml"


def test_nas_ollama_is_loopback_only_and_hardened():
    service = yaml.safe_load(COMPOSE_FILE.read_text())["services"]["ollama"]

    assert service["image"].startswith("${OLLAMA_IMAGE:?")
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
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges=true" in service["security_opt"]