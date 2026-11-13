from radar.core.secrets import scan_text, secret_values


def test_secrets_detects_token_shapes_without_values():
    found = scan_text("token=ghp_" + "a" * 36, secrets=[])
    assert found == ["GitHub 토큰"]
    assert scan_text("key sk-ant-" + "x" * 30, secrets=[]) == ["Anthropic 키"]


def test_secrets_detects_real_env_values():
    env = {"NOTION_TOKEN": "plainvalue123", "OTHER": "ignored-value"}
    vals = secret_values(env)
    assert vals == ["plainvalue123"]
    assert scan_text("x plainvalue123 y", secrets=vals) == ["실제 키 값"]
    assert scan_text("ignored-value", secrets=vals) == []


def test_secrets_ignores_short_values():
    assert scan_text("abc", secrets=["abc"]) == []
