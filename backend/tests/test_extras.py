"""NEW (v6): history, dashboard and fine-tuning endpoints."""
import json

import pytest
from fastapi.testclient import TestClient
from synth import make_synthetic

import insights
import tuning


@pytest.fixture
def client(tmp_path, monkeypatch):
    p = tmp_path / "s.csv.gz"
    make_synthetic().to_csv(p, index=False)
    monkeypatch.setenv("ARGO_DATA", str(p))
    monkeypatch.setattr(tuning, "DIR", tmp_path / "ft")
    monkeypatch.setattr(tuning, "RUNS", tmp_path / "ft" / "runs.json")
    import app
    app.llm_fn = None
    with TestClient(app.app) as c:
        yield c


Q = "What was the average temperature at 500 m in the Arabian Sea during 2024?"


def test_ask_is_recorded_and_answer_is_unchanged(client):
    a = client.post("/ask", json={"question": Q, "session_id": "s1"}).json()
    assert a["status"] in ("ok", "no_data")                       # the original answer still comes back intact
    h = client.get("/history").json()["sessions"]
    assert len(h) == 1 and h[0]["session_id"] == "s1" and h[0]["title"] == Q and h[0]["region"] == "arabian sea"
    t = client.get("/history/s1").json()["turns"]
    assert t[0]["answer"]["status"] == a["status"]                # resume-chat can redraw the card


def test_follow_up_joins_same_conversation_and_delete_works(client):
    client.post("/ask", json={"question": Q, "session_id": "s1"})
    client.post("/ask", json={"question": "What does QC flag 1 mean?", "session_id": "s1"})
    assert client.get("/history").json()["sessions"][0]["messages"] == 4
    assert client.delete("/history/s1").json()["deleted"] == 2
    assert client.get("/history/s1").status_code == 404


def test_dashboard_cold_start_and_after_questions(client):
    d = client.get("/dashboard").json()
    assert d["questions"] == 0 and "No questions yet" in d["summary"] and d["metrics"]["floats"] == 7
    assert d["recommendations"]                                   # recommendations exist even with no history
    client.post("/ask", json={"question": Q, "session_id": "s1"})
    d = client.get("/dashboard").json()
    assert d["questions"] == 1 and d["focus"]["label"] == "Arabian Sea · temperature" and d["topics"][0]["pct"] == 100
    assert any(r["tag"] == "OTHER VARIABLE" for r in d["recommendations"])   # asked temperature -> suggest salinity


def test_recommended_questions_are_answerable_by_the_rule_parser(client):
    from rules import parse_rules
    for r in client.get("/dashboard").json()["recommendations"]:
        if r["tag"] != "DATA QUALITY":
            parse_rules(r["question"])                            # must not raise Unsupported


def test_metrics_are_computed_from_the_table(client):
    import app
    m = insights.data_metrics(app.STATE["df"])
    assert m["synthetic"] and 0 <= m["qc_good_pct"] <= 100 and m["deepest_dbar"] > 0


def test_tuning_generate_then_evaluate_rules(client):
    assert client.post("/tuning/evaluate", json={"mode": "rules"}).status_code == 400          # nothing generated yet
    g = client.post("/tuning/generate", json={"n": 100}).json()
    assert g["train_rows"] > 0 and g["ready"]
    e = client.post("/tuning/evaluate", json={"mode": "rules", "limit": 50}).json()
    assert e["n"] > 0 and 0 <= e["accuracy"] <= 1 and e["runs"][0]["mode"] == "rules"
    assert client.post("/tuning/evaluate", json={"mode": "llm"}).status_code == 400            # no model configured
    assert len(client.get("/tuning/status").json()["runs"]) == 1


def test_tuning_llm_mode_uses_the_model(client, monkeypatch):
    client.post("/tuning/generate", json={"n": 100})
    import app
    seen = []
    def fake(system, user, json_mode):
        seen.append(1)
        raise RuntimeError("down")
    app.llm_fn = fake
    e = client.post("/tuning/evaluate", json={"mode": "llm", "limit": 3}).json()
    assert seen and e["accuracy"] == 0 and e["failures"]
