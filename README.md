# TalentServ AI Hackathon — Group 10 Backend

FastAPI service with Auth0 JWT auth and MySQL (Railway).

## Local setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| GET | `/api/v1/me` | Bearer JWT | Current user profile |
| POST | `/api/v1/data/ingest` | Admin key (dev: optional) | Load fallback CSV datasets |
| POST | `/api/v1/data/upload` | Bearer JWT | Upload CSV/XLSX property data |
| GET | `/api/v1/data/upload/templates/{dataset_type}` | No | Column template for uploads |
| GET | `/api/v1/data/scrape/sources` | No | Supported live scrape portals |
| POST | `/api/v1/data/scrape` | Bearer JWT | Scrape NoBroker/Housing/MagicBricks/99acres |
| GET | `/api/v1/properties` | No | List/query ingested properties (filters: city, bedrooms, budget, intent, …) |
| GET | `/api/v1/properties/{id}` | No | Get single property |
| POST | `/api/v1/properties/match` | Optional JWT | Rank listings against parsed requirement (`text` or `requirement_id`) |
| GET | `/api/v1/favorites` | Bearer JWT | List saved properties |
| POST | `/api/v1/favorites` | Bearer JWT | Save a property favorite |
| DELETE | `/api/v1/favorites?listing_key=` | Bearer JWT | Remove a favorite |
| POST | `/api/v1/inquiries` | Bearer JWT | Submit contact/inquiry form |
| POST | `/api/v1/requirements/parse` | No | Parse NL requirement text |
| POST | `/api/v1/requirements` | Bearer JWT | Save parsed requirement |
| GET | `/api/v1/requirements/latest` | Bearer JWT | Latest saved requirement |

## Phase 1 — Seed demo data

```bash
# After migrations
curl -X POST http://localhost:8000/api/v1/data/ingest

# Query properties
curl "http://localhost:8000/api/v1/properties?source=housing&page=1"
```

Fallback CSVs live in `data/`. See [data/README.md](data/README.md) and [docs/COMPLIANCE.md](../docs/COMPLIANCE.md).

Re-running ingest is idempotent — existing `(source, external_id)` rows are updated, not duplicated.

## Phase 2 — Requirement parsing

```bash
curl -X POST http://localhost:8000/api/v1/requirements/parse \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"2 BHK flat for rent in Hinjewadi, Pune under 50 lakh\"}"

pytest tests/test_parser.py
```

Optional LLM enhancement: set `OPENAI_API_KEY` in `.env`.

## Phase 3 — Property matching

```bash
curl -X POST http://localhost:8000/api/v1/properties/match \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"2 bedroom apartment for rent in Bengaluru under 35000\"}"

pytest tests/test_matching.py
```

Response includes ranked `items` with `score` (0–1) and human-readable `reasons`, plus the `parsed` requirement.

## Phase 4 — Favorites, inquiries, and property detail

```bash
# List favorites (Bearer token required)
curl http://localhost:8000/api/v1/favorites -H "Authorization: Bearer $TOKEN"

# Save a favorite
curl -X POST http://localhost:8000/api/v1/favorites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"listing_key\":\"db:1\",\"property_id\":1}"

# Submit inquiry
curl -X POST http://localhost:8000/api/v1/inquiries \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"listing_key\":\"db:1\",\"property_id\":1,\"name\":\"Jane\",\"email\":\"jane@example.com\",\"message\":\"I would like to schedule a visit.\"}"
```

Run migration: `alembic upgrade head`

## Railway deployment

1. Create a new Railway project and add **MySQL**.
2. Add a service from this repo with root directory `talentserv-ai-hackathon-group-10-backend`.
3. Set environment variables from `.env.example` (Railway injects `DATABASE_URL` from MySQL).
4. Set `CORS_ORIGINS` to your Vercel frontend URL.
5. Deploy — migrations run automatically via `railway.toml` start command.

## Auth0 API setup

1. Create an API in Auth0 with identifier matching `AUTH0_API_AUDIENCE`.
2. Enable RBAC later as needed; Phase 0 only requires a valid access token.
3. Ensure the SPA requests this audience when logging in.
