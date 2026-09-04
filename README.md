# Super Mega Data Gatherer

> Gathers support data for the Super Mega Dashboard

## Configuration

A `config.yaml` file is used to configure this Super Mega Data Gatherer.

Config values are interpreted using [Jinja](https://jinja.palletsprojects.com/),
allowing secrets to be interpolated using environment variables (see `config.yaml` for examples).

Configuration for the main instance (for Hack Club Stardance) is committed to
this repository and used by default. For self-hosting, you can
provide a path to your own config file using the `--config` CLI argument.

Uhh I don't have any documentation for the config format but it should be relatively
obvious. You can always DM @Mish on Slack :)

## API

- `GET /api/v2/{event}/super-mega-stats?start=YYYY-MM-DD&end=YYYY-MM-DD` - stats
  for a specific event, e.g.
  <http://localhost:8000/api/v2/stardance/super-mega-stats?start=2026-01-01&end=2026-01-15>

### Legacy endpoints

- `GET /api/v1/super-mega-stats` - stats for the `flavortown`
  event

## Running in development

### Preparation

This project uses Python and `uv`. Start by installing dependencies:

```bash
uv sync
```

And then set environment variables:

```bash
cp .env.example .env
$EDITOR .env
```

### Run it!

Run the API with hot reloading for development:

```bash
uv run fastapi dev
```

## Running in production (without Docker)

I'd recommend using Uvicorn, e.g.

```bash
uv run uvicorn main:app --port <PORT>
```
