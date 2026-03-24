# Super Mega Data Gatherer

> Gathers support data for the Super Mega Dashboard

## Usage

### Requirements

This project uses Python and `uv`. Start by installing dependencies:

```bash
uv sync
```

And then set environment variables:

```bash
cp .env.example .env
$EDITOR .env
```

### Running in development

Run the API with hot reloading for development:

```bash
uv run fastapi dev
```

See it working at <http://localhost:8000/api/v1/super-mega-stats?start=2026-01-01&end=2026-01-15>

### Running in production

I'd recommend using Uvicorn, e.g.

```bash
uv run uvicorn main:app --port <PORT>
```
