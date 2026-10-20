# Cecilia Clinic Supply Renewal

Cecilia watches annual supply agreements for clinics. It shows which clinics are likely to let the contract lapse, how much contract value is exposed, when the term ends, and what to do before that date.

A user opens the Streamlit workspace, filters the book, and runs a clinic analysis. The analysis returns a lapse score, the drivers behind it, prior notes, the matching supply playbooks, a reviewed action plan, and a short report. Opening a follow-up ticket stays behind an explicit approval.

## What it does

1. Loads labeled clinic history and the current book of active agreements.
2. Checks the files and writes them to SQLite.
3. Trains a lapse model on the history and scores the current book.
4. Ranks clinics on a save desk, not by probability alone.
5. Serves that book through FastAPI and Streamlit.

Save priority is lapse probability × contract value at risk × term pressure. Term inside 30 days has pressure 1.0, inside 60 days 0.75, inside 120 days 0.45, and later than that 0.2.

| Lane | Meaning |
| --- | --- |
| Call today | High lapse risk, term inside 30 days |
| This cycle | High or medium risk, term inside 90 days |
| Watch | Everyone else |

A high-risk clinic inside 45 days of term also uses the `save-desk-triage` skill.

## Stack

| Layer | What it uses |
| --- | --- |
| Language | Python 3.11 |
| API | FastAPI |
| UI | Streamlit |
| Database | SQLite |
| Records | Clinic history, current clinics, scores, memory, tickets, feedback |
| Lapse model | Logistic regression, stored with joblib |
| Retrieval | Lexical TF-IDF over `data/knowledge` |
| Decision workflow | Deterministic provider |
| Skills | Local files in `skills/` |
| Config | `.env` |

`AGENT_PROVIDER` is `deterministic`. `RETRIEVAL_BACKEND` is `lexical`. This run does not call an external model API.

Clinic fields are the supply agreement, not a software seat: stocked cabinets, active cabinet ratio, buyers, orders, service tickets, invoice failures, and days to term. Identifiers look like `CLN-0042`. Segments are Community, Specialty, and Health System.

## Run

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.bootstrap
python -m scripts.demo
```

`scripts.bootstrap` writes `data/raw/clinic_history.csv` and `data/raw/current_clinics.csv`, loads SQLite, trains the model, and scores the current book.

API:

```bash
uvicorn app.api.main:app --reload
```

UI, in a second terminal:

```bash
streamlit run app/ui/streamlit_app.py
```

## API

- `GET /health`
- `GET /v1/clinics/{clinic_id}`
- `GET /v1/clinics/high-risk?limit=10`
- `GET /v1/operations/dashboard`
- `POST /v1/analysis`
- `POST /v1/feedback`

```bash
curl -X POST http://localhost:8000/v1/analysis \
  -H 'Content-Type: application/json' \
  -d '{"clinic_id":"CLN-0001","session_id":"demo","create_ticket":false}'
```

## Layout

```text
Streamlit / FastAPI
        ↓
Clinic term workflow
        ↓
Model, clinic facts, supply playbooks, memory
        ↓
Recommendation, review, report
        ↓
SQLite, model file, knowledge documents
```
