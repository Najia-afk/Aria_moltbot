from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "capture_image_provenance.sh"


def test_image_provenance_capture_is_non_destructive_and_secret_averse():
    source = SCRIPT.read_text()

    assert "docker compose" in source
    assert "config --images" in source
    assert "docker image inspect" in source
    assert "docker ps --format" in source
    assert "docker pull" not in source
    assert "docker compose pull" not in source
    assert "docker build" not in source
    assert "docker save" not in source
    assert "docker inspect" not in source
    assert "Config.Env" not in source
    assert "docker compose config >" not in source