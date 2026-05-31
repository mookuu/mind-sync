from app.services.security import collect_security_warnings


def test_collect_security_warnings_defaults():
    warnings = collect_security_warnings()
    assert any("AUTH_PASSWORD" in w for w in warnings)
    assert any("API_KEY" in w for w in warnings)
