"""설정 읽기 — config/settings.toml (표준 라이브러리 tomllib)."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "settings.toml"
SIGNALS = ("s1", "s2", "s3", "s4", "s5")


class ConfigError(Exception):
    """설정 파일이 잘못됐다."""


@dataclass(frozen=True)
class Config:
    startrend_dir: Path
    cap: int
    previous_top: int
    weights: dict[str, int]
    weights_version: int


def load_config(path: Path = DEFAULT_SETTINGS, env: Mapping[str, str] | None = None) -> Config:
    """설정을 읽고 검증한다. env 는 테스트에서 바꿔 넣는다."""
    import os

    env = os.environ if env is None else env
    try:
        raw: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
        w = raw["weights"]
        weights = {k: int(w[k]) for k in SIGNALS}
        cfg_dir = env.get("RADAR_STARTREND_DIR") or str(path.parent / raw["startrend"]["dir"])
        cfg = Config(Path(cfg_dir).resolve(), int(raw["candidates"]["cap"]),
                     int(raw["candidates"]["previous_top"]), weights, int(w["version"]))
    except (OSError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"설정을 읽지 못했다 ({path.name}: {e})") from e
    if sum(weights.values()) != 100:
        raise ConfigError(f"가중치 합이 100 이 아니다 ({sum(weights.values())})")
    if cfg.cap <= 0:
        raise ConfigError("candidates.cap 은 1 이상")
    return cfg
