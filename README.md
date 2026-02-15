# Super Mega Data Gatherer

> Gathers support data for the Super Mega Dashboard

## Usage

### Requirements

This project uses Python and `uv`. Start by installing dependencies:

```bash
uv sync
```

### Running in development

Run the API with hot reloading for development:

```bash
uv run fastapi dev
```

### Running in production

I'd recommend using Uvicorn, e.g.

```bash
uv run uvicorn main:app --port <PORT>
```
