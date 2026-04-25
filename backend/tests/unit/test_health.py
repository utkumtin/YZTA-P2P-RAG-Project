from app.api.routes.health import health_check


async def test_health_status_ok():
    result = await health_check()
    assert result["status"] == "ok"


async def test_health_has_app_and_version():
    result = await health_check()
    assert "app" in result
    assert "version" in result
    assert result["app"] is not None
