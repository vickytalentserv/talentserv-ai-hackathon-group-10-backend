# TalentServ AI Hackathon — Group 10 Backend

FastAPI service with Auth0 JWT auth and MySQL (Railway).

## Local setup

```bash
python -m venv venv
source venv/bin/activate          # macOS/Linux
pip install -r requirements.txt
playwright install chromium       # required only for Housing.com live scraping
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Python **3.12+** is recommended (the codebase uses modern type syntax).

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| GET | `/api/v1/me` | Bearer JWT | Current user profile |
| POST | `/api/v1/data/ingest` | Admin key (dev: optional) | Load fallback CSV datasets |
| POST | `/api/v1/data/upload` | Bearer JWT | Upload CSV/XLSX property data |
| GET | `/api/v1/data/upload/templates/{dataset_type}` | No | Column template for uploads |
| GET | `/api/v1/data/scrape/sources` | No | Supported live scrape portals |
| POST | `/api/v1/data/scrape` | Bearer JWT | Scrape live listings from Indian property portals |
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

Fallback CSVs live in `data/`. See [data/README.md](data/README.md).

Re-running ingest is idempotent — existing `(source, external_id)` rows are updated, not duplicated.

## Phase 2 — Live web scraping

Fetch real listings from Indian property portals and upsert them into MySQL. The frontend **Upload** page (`/upload` → **Fetch live data**) calls this endpoint.

### Supported sources

| Source | Method | Notes |
|--------|--------|-------|
| `nobroker` | NoBroker JSON API (`httpx`) | Most reliable; no browser required |
| `magicbricks` | HTML fetch + parser (`httpx`) | Parses listing cards from search pages |
| `housing` | Playwright (Chromium) | Runs in an isolated thread to avoid FastAPI/asyncio conflicts; may hit bot detection intermittently |
| `99acres` | HTML fetch (`httpx`) | Often blocked by `robots.txt` |

Supported cities: **Pune**, **Mumbai**, **Bengaluru** (also accepts `Bangalore`).

### Environment variables

```env
SCRAPE_ENABLED=true
SCRAPE_DELAY_SECONDS=2.0
SCRAPE_PLAYWRIGHT_ENABLED=true
SCRAPE_PLAYWRIGHT_HEADLESS=true
SCRAPE_PLAYWRIGHT_CHANNEL=          # leave empty for bundled Chromium; avoid `chrome` locally unless needed
SCRAPE_PLAYWRIGHT_TIMEOUT_MS=45000
```

Set `SCRAPE_ENABLED=false` to disable scraping on a deployed server.

### Scrape via API

```bash
# List supported portals
curl http://localhost:8000/api/v1/data/scrape/sources

# Scrape NoBroker + MagicBricks for Pune sale listings (Bearer token required)
curl -X POST http://localhost:8000/api/v1/data/scrape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["nobroker", "magicbricks"],
    "city": "Pune",
    "listing_status": "for_sale",
    "max_results": 20
  }'
```

Request body:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sources` | `string[]` | — | One or more of `nobroker`, `housing`, `magicbricks`, `99acres` |
| `city` | `string` | `Pune` | City to search |
| `listing_status` | `for_sale` \| `for_rent` | `for_sale` | Buy/sale vs rent |
| `max_results` | `int` | `20` | Max listings per source (1–50) |

Response includes per-source `fetched`, `parsed`, `blocked_by_robots`, and ingest totals (`rows_inserted`, `rows_updated`).

### Verify scraped data

```bash
# List scraped listings
curl "http://localhost:8000/api/v1/properties?city=Pune&source=nobroker&listing_status=for_sale"

# Match against AI search (use buy/sale wording for for_sale data)
curl -X POST http://localhost:8000/api/v1/properties/match \
  -H "Content-Type: application/json" \
  -d '{"text":"2 BHK flat for sale in Pune under 80 lakh"}'
```

Example Dashboard prompts for Pune sale data:

- `I want a 2BHK property in Pune`
- `2 BHK flat for sale in Pune under 80 lakh`
- `2 bedroom apartment to buy in Hinjewadi Pune under 1 crore`

### Compliance and limitations

- Every request checks the site’s `robots.txt` and rate-limits fetches (`SCRAPE_DELAY_SECONDS`).
- Sites may block bots intermittently — **CSV upload** (`POST /api/v1/data/upload`) remains the primary fallback.
- Scraped rows upsert on `(source, external_id)`; re-scraping updates existing rows instead of duplicating them.
- For a clean test run, clear property rows in MySQL before scraping so the response shows `rows_inserted` instead of `rows_updated`.

### Tests

```bash
pytest tests/test_scrape_parsers.py
```

## Phase 3 — Requirement parsing

```bash
curl -X POST http://localhost:8000/api/v1/requirements/parse \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"2 BHK flat for rent in Hinjewadi, Pune under 50 lakh\"}"

pytest tests/test_parser.py
```

Optional OpenAI enhancement: set `OPENAI_API_KEY` in `.env`.

When enabled, the backend uses OpenAI to:
- improve natural-language query parsing (`rules+llm` in the parse response)
- rerank the top property matches with clearer reasons (`source: database+llm`)

Tune with `OPENAI_MATCH_RERANK`, `OPENAI_MATCH_RERANK_LIMIT`, and `OPENAI_ENABLED`.
Check `/health` for `openai_enabled: true`.

The rules parser understands phrases like `Pune area` as city scope (not a locality filter).

## Phase 4 — Property matching

```bash
curl -X POST http://localhost:8000/api/v1/properties/match \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"2 bedroom apartment for rent in Bengaluru under 35000\"}"

pytest tests/test_matching.py
```

Response includes ranked `items` with `score` (0–1) and human-readable `reasons`, plus the `parsed` requirement.

Bedroom filters use **exact BHK count** when specified (e.g. `2 BHK` matches only 2-bedroom listings).

## Phase 5 — Favorites, inquiries, and property detail

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

**Live scraping on Railway:** Housing.com requires Playwright/Chromium. You may need extra Nixpacks setup or a custom Docker image with browser dependencies. NoBroker and MagicBricks work over plain HTTP and are more deployment-friendly. Set `SCRAPE_ENABLED=false` if scraping is not configured on the host.

## Auth0 API setup

1. Create an API in Auth0 with identifier matching `AUTH0_API_AUDIENCE`.
2. Enable RBAC later as needed; Phase 0 only requires a valid access token.
3. Ensure the SPA requests this audience when logging in.
