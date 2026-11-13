# FILE: tests/test_api.py - API tests with a scripted fake LLM. CHANGED (v2): strict PARSER=llm for the "LLM down" case.
import json, os
import pytest
from fastapi.testclient import TestClient
from synth import make_synthetic

GOOD = {"intent": "mean_at_depth", "variable": "temperature", "region": "Arabian Sea",
        "start": "2024-01-01", "end": "2024-12-31", "depths_m": [500]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    p = tmp_path / "s.csv.gz"
    make_synthetic().to_csv(p, index=False)
    monkeypatch.setenv("ARGO_DATA", str(p))
    import app
    with TestClient(app.app) as c:
        c.mod = app
        yield c


def stub(parse, explain="The temperature was 23.00 °C."):
    return lambda system, user, json_mode: json.dumps(parse) if json_mode else explain


def test_health(client):
    h = client.get("/health").json()
    assert h["loaded"] and h["floats"] == 7 and "SYNTHETIC" in h["source"]


def test_ask_happy_path_numbers_come_from_engine(client):
    client.mod.llm_fn = stub({**GOOD, "intent": "mean_at_depth"}, "LLM says it was 99 degrees.")
    a = client.post("/ask", json={"question": "x"}).json()
    assert a["status"] == "ok" and a["result"]["series"][0]["value"] == pytest.approx(23.0)
    assert "23.00" in a["explanation"]  # LLM text lacked the verified number -> deterministic summary used


def test_llm_explanation_kept_when_it_contains_verified_number(client):
    client.mod.llm_fn = stub(GOOD, "Mean was 23.00 °C across 50 profiles.")
    assert client.post("/ask", json={"question": "x"}).json()["explanation"].startswith("Mean was 23.00")


def test_unsupported_and_invalid_and_llm_down(client, monkeypatch):
    client.mod.llm_fn = stub({"unsupported": "forecasts are not supported"})
    assert client.post("/ask", json={"question": "x"}).json()["status"] == "unsupported"
    client.mod.llm_fn = stub({**GOOD, "region": "atlantis"})
    assert client.post("/ask", json={"question": "x"}).json()["status"] == "unsupported"
    def boom(*a): raise RuntimeError("no key")
    client.mod.llm_fn = boom
    monkeypatch.setenv("PARSER", "llm")  # CHANGED (v2): strict mode reports the LLM failure; default 'auto' falls back to rules
    assert client.post("/ask", json={"question": "x"}).json()["status"] == "error"


def test_query_endpoint_works_without_llm(client):
    client.mod.llm_fn = None
    a = client.post("/query", json={**GOOD, "intent": "compare_depths", "depths_m": [100, 1000]}).json()
    assert a["status"] == "ok" and a["result"]["difference"] == pytest.approx(-9.0)
