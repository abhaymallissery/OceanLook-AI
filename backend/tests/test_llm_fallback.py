"""NEW (v4): Gemini -> Groq -> raise, cooldown, and .env loading."""
import os
import time

import pytest

import config
import llm


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    llm._DOWN.clear()
    for k in ("OLLAMA_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_no_key_means_no_llm():
    assert not llm.has_llm()


def test_groq_used_when_gemini_fails(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x"); monkeypatch.setenv("GROQ_API_KEY", "y")
    calls = []
    def bad(*a): calls.append("gemini"); raise TimeoutError()
    monkeypatch.setattr(llm, "gemini", bad)
    monkeypatch.setattr(llm, "groq", lambda *a: calls.append("groq") or "ok")
    assert llm.chat("s", "u", False) == "ok"
    t = time.time(); assert llm.chat("s", "u", False) == "ok"
    assert calls == ["gemini", "groq", "groq"]  # gemini skipped during cooldown: second call is instant


def test_all_fail_raises_so_rules_take_over(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "y")
    monkeypatch.setattr(llm, "groq", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        llm.chat("s", "u", True)
    q, used = llm.parse_auto("Average temperature at 500 m in the Arabian Sea in 2024?", llm.chat)
    assert used == "rules" and q.depths_m == [500]


def test_env_file_loaded_but_real_env_wins(tmp_path, monkeypatch):
    f = tmp_path / ".env"; f.write_text('# c\nGROQ_API_KEY="abc"\nGEMINI_API_KEY=real\n')
    monkeypatch.setenv("GEMINI_API_KEY", "shell")
    config.load_env(f)
    assert os.environ["GROQ_API_KEY"] == "abc" and os.environ["GEMINI_API_KEY"] == "shell"
    monkeypatch.delenv("GROQ_API_KEY")


def test_ollama_first_then_gemini(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "m"); monkeypatch.setenv("GEMINI_API_KEY", "x")
    seen = []
    monkeypatch.setattr(llm, "ollama", lambda *a: seen.append("ollama") or "local")
    assert llm.chat("s", "u", False) == "local" and seen == ["ollama"]
    monkeypatch.setattr(llm, "ollama", lambda *a: (_ for _ in ()).throw(ConnectionError()))
    llm._DOWN.clear()
    monkeypatch.setattr(llm, "gemini", lambda *a: "cloud")
    assert llm.chat("s", "u", False) == "cloud"


def test_fast_mode_uses_rules_first_and_llm_only_when_rules_cannot(monkeypatch):
    calls = []
    def fake(system, user, json_mode):
        calls.append(1)
        return '{"intent":"mean_at_depth","variable":"temperature","region":"arabian sea","start":"2024-01-01","end":"2024-12-31","depths_m":[500],"statistic":"mean"}'
    q, used = llm.parse_auto("Average temperature at 500 m in the Arabian Sea in 2024?", fake, mode="fast")
    assert used == "rules" and calls == []                       # clear question: no LLM call at all
    q, used = llm.parse_auto("how warm is it half a kilometre down in the Arabian Sea, 2024", fake, mode="fast")
    assert used == "llm" and calls == [1]                        # rules cannot read it: LLM helps
