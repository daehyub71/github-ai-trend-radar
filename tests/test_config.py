import pytest

from radar.config import ConfigError, load_config

GOOD = """
[startrend]
dir = "../github-ai-star-trend"

[candidates]
cap = 200
previous_top = 10

[weights]
version = 1
s1 = 15
s2 = 15
s3 = 25
s4 = 30
s5 = 15
"""


def test_config_loads(tmp_path):
    (tmp_path / "settings.toml").write_text(GOOD, encoding="utf-8")
    c = load_config(tmp_path / "settings.toml", env={})
    assert c.cap == 200 and c.previous_top == 10
    assert c.weights == {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15} and c.weights_version == 1
    assert c.startrend_dir == (tmp_path / "../github-ai-star-trend").resolve()


def test_config_env_overrides_startrend_dir(tmp_path):
    (tmp_path / "settings.toml").write_text(GOOD, encoding="utf-8")
    c = load_config(tmp_path / "settings.toml", env={"RADAR_STARTREND_DIR": str(tmp_path / "st")})
    assert c.startrend_dir == (tmp_path / "st").resolve()


def test_config_weights_must_sum_to_100(tmp_path):
    (tmp_path / "settings.toml").write_text(GOOD.replace("s5 = 15", "s5 = 10"), encoding="utf-8")
    with pytest.raises(ConfigError, match="100"):
        load_config(tmp_path / "settings.toml", env={})


def test_config_repo_settings_file_is_valid():
    c = load_config()
    assert sum(c.weights.values()) == 100


def test_config_angles_loaded_from_settings():
    from radar.config import load_config
    from radar.core.angles import RULES_V1

    cfg = load_config()
    assert cfg.angles == RULES_V1


def test_config_insights_loaded_from_settings():
    from radar.config import load_config
    from radar.core.insights import RULES_V1

    assert load_config().insights == RULES_V1
