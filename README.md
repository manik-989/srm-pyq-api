# SRM Resources API (Deploy-Only Package)

This folder contains only the files needed to run and deploy the SRM Resources API.

## Included Files

- `api_server.py` — FastAPI app
- `api_client.py` — CLI client for manual endpoint checks
- `api_smoke_test.py` — Integration smoke test script
- `requirements.txt` — Minimal API dependencies
- `.env.example` — Environment variable template
- `Procfile` — Standard process command for many PaaS providers
- `.gitignore` — Excludes local/dev artifacts

## API Endpoints

- `GET /health`
- `GET /ready`
- `GET /v1/courses?q=&cursor=&limit=`
- `GET /v1/courses/{course_code}`
- `GET /v1/courses/{course_code}/papers?year=&term=&cursor=&limit=`
- `GET /v1/papers/{paper_id}`
- `GET /v1/papers/{paper_id}/files`
- `GET /v1/files/{file_id}/download?ttl_seconds=900`

`q` in `/v1/courses` matches `course_code`, `course_name`, and `course_abbreviation` (when the column is present).

## Local Run

```bash
python -m pip install -r requirements.txt
cp .env.example .env
# fill real values in .env
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

## Local Validation

```bash
python api_smoke_test.py --base-url http://127.0.0.1:8000
```

## DevOps

- Install dev tools: `pip install -r requirements-dev.txt`
- Lint and format: `ruff check . && ruff format --check .`
- Tests: `pytest` (contract tests use an in-memory Supabase fake, so no credentials or network are required)
- Coverage: `pytest --cov=api_server --cov-report=term-missing` (80% floor enforced)
- Docker image: `docker build -t srm-pyq-api .`
- Full stack: `docker compose up --build` from the workspace root
- CI: `.github/workflows/ci.yml` runs lint, tests on Python 3.11-3.13, Docker build, and a Trivy image scan
- Security: CodeQL (weekly), Dependabot (weekly), and an advisory `pip-audit` job
- Probes: `/health` is liveness; `/ready` also checks Supabase connectivity

See the workspace root `README.md` for the full DevOps guide.

## Deploy (Render / Railway / Fly / similar)

- Build/install: `pip install -r requirements.txt`
- Start: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`

Set environment variables in the platform dashboard:

### Supabase
- `SUPABASE_URL` (or `PROJECT_ID`)
- `SUPABASE_SERVICE_ROLE_KEY`

### Cloudflare R2
- `R2_ENDPOINT_URL` (or `CLOUDFLARER2_S3_API` / `CLOUDFLARE_ENDPOINTS`)
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`
- `R2_PUBLIC_BASE_URL` (optional)

## Post-Deploy Access

If deployed at `https://your-api.example.com`, access:

- `https://your-api.example.com/health`
- `https://your-api.example.com/v1/courses?limit=5`

Run smoke tests against deployed API:

```bash
python api_smoke_test.py --base-url https://your-api.example.com
```
