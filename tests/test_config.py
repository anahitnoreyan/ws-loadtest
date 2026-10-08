import pytest

from wsload.config import LoadConfig, load_config


def test_load_config_from_yaml(tmp_path):
    path = tmp_path / "scenario.yaml"
    path.write_text(
        "name: t\nuri: ws://127.0.0.1:9000\nconnections: 5\n"
        "thresholds:\n  max_p95_ms: 100\n",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.name == "t"
    assert cfg.connections == 5
    assert cfg.thresholds.max_p95_ms == 100


def test_misspelled_key_is_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("conections: 5\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize("kwargs", [
    {"connections": 0},
    {"messages_per_connection": 0},
    {"uri": "http://example.com"},
    {"response_timeout_s": 0},
])
def test_invalid_values_are_rejected(kwargs):
    with pytest.raises(ValueError):
        LoadConfig(**kwargs).validate()
