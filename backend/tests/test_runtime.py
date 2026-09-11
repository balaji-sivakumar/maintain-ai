from runtime import setup_telemetry


def test_setup_telemetry_is_a_noop_without_an_otlp_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert setup_telemetry() is None


def test_setup_telemetry_configures_an_exporter_when_endpoint_is_set(monkeypatch):
    # Constructing the OTLP exporter doesn't make a network call — it only
    # sends on flush — so this is safe to test without a real collector.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:1")
    telemetry = setup_telemetry()
    assert telemetry is not None
    assert telemetry.tracer_provider is not None
