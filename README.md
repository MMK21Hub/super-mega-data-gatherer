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

### Configuration

All configuration lives in `config.yaml`, which is committed to the repo. It's a
nested map of keys to strings, so it can safely be public. Every string is rendered
once at startup as a [Jinja](https://jinja.palletsprojects.com/) template in a
restrictive sandboxed environment whose only extra variable is `env` - a read-only
view of the environment variables. That's how secrets like database URLs are
interpolated without ever being committed:

```yaml
nephthys_db_url: "{{ env.STARDANCE_NEPHTHYS_DATABASE_URL }}"
```

Set `CONFIG_PATH` to load a config file from somewhere else.

Events are configured as a map of event slugs to their config, and the slug becomes
part of the API path:

```yaml
events:
  stardance:
    nephthys_db_url: "{{ env.STARDANCE_NEPHTHYS_DATABASE_URL }}"
    prometheus_labels:
      job: "support_watcher_stardance"
```

### API

- `GET /api/v2/{event}/super-mega-stats?start=YYYY-MM-DD&end=YYYY-MM-DD` — stats
  for a specific event, e.g.
  <http://localhost:8000/api/v2/stardance/super-mega-stats?start=2026-01-01&end=2026-01-15>
- `GET /api/v1/super-mega-stats` — legacy endpoint, always serves the `flavortown`
  event

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
