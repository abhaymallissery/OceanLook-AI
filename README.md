# OceanLook (SIH25040) - Flutter + Python
OceanLook enables natural plain-English exploration and analysis of ARGO ocean float data.

## Quick start
```bash
cd backend && pip install -r requirements.txt
python -m pytest -q                                   # 66 tests

# A) real data, official GDAC files (recommended). Try one week first:
python fetch_gdac.py --region "arabian sea" --start 2024-01-01 --end 2024-01-07
#    full year:  --start 2024-01-01 --end 2024-12-31
# B) real data through ERDDAP:  python fetch_subset.py --region "arabian sea" --start 2024-01-01 --end 2024-12-31
#    (or download in a browser, then: python convert_manual.py data/raw/*.csv)
# C) no real data yet? just start the app: it falls back to labelled SYNTHETIC demo data and says so everywhere.

cp .env.example .env                                  # NEW (v4): put GEMINI_API_KEY and/or GROQ_API_KEY in .env (private, git-ignored)
export ARGO_DATA=data/argo_subset.csv.gz              # Windows: set ARGO_DATA=...
uvicorn app:app --reload                              # works without any API key (offline rule parser)
python eval_run.py --data $ARGO_DATA --parser rules --report REPORT.md

# Flutter
cd ../flutter_app && flutter create . --platforms=web,android,ios && flutter pub get
flutter run -d chrome --dart-define=API_BASE=http://localhost:8000
```

## Local LLM with Ollama (first choice, no key, no internet)
```bash
# install from https://ollama.com/download, then:
ollama pull llama3.2 && ollama serve        # serve may already run in the background
# backend/.env already has OLLAMA_MODEL=llama3.2 (delete the line to skip Ollama)
```
If Ollama is not running, the first question skips it instantly (connection refused) and the app moves to Gemini, then Groq, then offline rules.

## Where to download the real ARGO data
Official pages: https://argo.ucsd.edu/data/ (overview) -> Argo GDAC. Download the **core profile files**, folder `geo/indian_ocean/YYYY/MM/YYYYMMDD_prof.nc`:
- https://data-argo.ifremer.fr/geo/indian_ocean/2024/01/  (Ifremer GDAC, France)
- https://usgodae.org/pub/outgoing/argo/geo/indian_ocean/2024/01/  (NOAA/USGODAE mirror)
Easiest: `python fetch_gdac.py --region "arabian sea" --start 2024-01-01 --end 2024-12-31` (tries both servers), or download files by hand into `data/raw/` and run `python convert_gdac.py`. Use 2023/2024 (mostly delayed-mode, scientist-checked).
If the real file is missing or cannot load, the app starts on labelled **SYNTHETIC** data automatically and says so in every answer.

## Manual download (use this when the script fails)
The GDAC page you opened is correct. Each file `YYYYMMDD_prof.nc` is one day for the whole Indian Ocean (about 4-8 MB).
1. Open https://data-argo.ifremer.fr/geo/indian_ocean/2024/01/ and save the files (right-click, Save link as), into `backend/data/raw/`.
   Start small: **January to March 2024 (about 90 files, roughly 450 MB)**. A full year is about 1.5 GB and takes longer.
   Faster: `python fetch_gdac.py --print-urls --start 2024-01-01 --end 2024-03-31 > urls.txt` and give the list to a download manager.
2. Build the table (no download is attempted):
   `python fetch_gdac.py --raw data/raw --region "arabian sea" --start 2024-01-01 --end 2024-03-31`
   Run it again with `--region "bay of bengal"` and the same files if you need that region too. Use `--out` for a second file name.
3. Start the app (`ARGO_DATA` defaults to `data/argo_subset.csv.gz`). `/health` must say the source is the official Argo GDAC, not SYNTHETIC.
Questions must stay inside the months you converted. NOAA mirror (usgodae.org) returned HTTP 500 on 2026-11-01; the script now uses Ifremer first and prints the error of every server.

## Which model, and can this laptop run it (Core Ultra 7 + Arc)
Nothing here needs training. The numbers come from the engine; the model only reads the question, and `PARSER=fast` skips it for clear questions.
- Recommended local model: `ollama pull llama3.2` (3B, already the default). If it feels slow, use `qwen2.5:1.5b` (set `OLLAMA_MODEL`).
- Ollama normally runs on the CPU on Windows with Intel Arc; expect roughly 5-15 tokens/second for a 3B model (estimate, not measured here; first call also loads the model).
  A question's JSON answer is about 80 tokens, so an LLM-parsed question takes several seconds; a rule-parsed question takes under a millisecond.
- Fine-tuning (LoRA) on an Arc integrated GPU is not practical. If you want it, run `make_finetune_data.py`, tune on free Google Colab (T4), and set `OLLAMA_MODEL`/`GEMINI_MODEL`; see EXPLANATION section 8.

## Optional switches (environment variables; see config.py)
`OLLAMA_MODEL` (local, first) / `GEMINI_API_KEY` / `GROQ_API_KEY` (in `backend/.env`; order Ollama -> Gemini -> Groq -> offline rules) · `LLM_TIMEOUT` · `PARSER=auto|llm|rules` · `FEWSHOT` · `MEMORY` · `RAG` · `AGENT=react` · `GUARDRAILS` · `ALLOW_SYNTHETIC` · `GEMINI_MODEL`

## Status
Tested here: engine, API, rules, verify, RAG, agent (scripted), guardrails, memory, NetCDF layout, fine-tune data (66 tests, incl. v4 fallback).
Not run here: real downloads, Gemini calls, Flutter build.


## The three pages (v6)
Research Hub (summary, recommendations), Chat (with History and Resume), Fine-tuning (make data, measure a model).
