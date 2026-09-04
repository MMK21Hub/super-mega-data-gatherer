# Super Mega Data Gatherer

> Gathers support data for the Super Mega Dashboard

## Quick start

**Access the public instance at <https://support-stats.slevel.xyz/>**

Example query: <https://support-stats.slevel.xyz/api/v2/stardance/super-mega-stats?start=2026-08-01&end=2026-08-31>

To run it yourself, see instructions below for [running in development](#running-in-development) or [deploying with Docker Compose](#running-in-production-docker-compose).

## API

- `GET /api/v2/{event}/super-mega-stats?start=YYYY-MM-DD&end=YYYY-MM-DD` - get support stats for a specific event and time period, e.g.
  <http://localhost:8000/api/v2/flavortown/super-mega-stats?start=2026-01-01&end=2026-01-15>

### Legacy endpoints

- `GET /api/v1/super-mega-stats` - stats for the `flavortown` event only

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

## Running in production (Docker Compose)

I recommend deploying this service using the provided Docker image.

Here's a `docker-compose.yaml` file that you can tweak to your liking:

```yaml
services:
  super-mega-data-gatherer:
    container_name: super-mega-data-gatherer
    image: ghcr.io/mmk21hub/super-mega-data-gatherer:latest
    ports:
      - 8000:8000
    restart: unless-stopped
    env_file: .env
```

Create a `.env` file to contain your secrets (see `.env.example`).

If you with to provide your own config file, create a `config.yaml` file based on [the default file](config.yaml) and mount it to the container by adding:

<!-- prettier-ignore -->
```yaml
    volumes:
      - ./config.yaml:/app/config.yaml:ro
```

## Running in production (without Docker)

I'd recommend using Uvicorn, e.g.

```bash
uv run uvicorn main:app --config [PATH]
```

How you handle environment variables is up to you.

## Configuration

A `config.yaml` file is used to configure this Super Mega Data Gatherer.

Config values are interpreted using [Jinja](https://jinja.palletsprojects.com/),
allowing secrets to be interpolated using environment variables (see `config.yaml` for examples).

Configuration for the main instance (for Hack Club Stardance) is committed to
this repository and used by default. For self-hosting, you can
provide a path to your own config file using the `--config` CLI argument.

Uhh I don't have any documentation for the config format but it should be relatively
obvious. You can always DM @Mish on Slack :)

## AI usage in this project

I've used GitHub Copilot for code completion, and Command Code to implement multi-event support.

All documentation is human-written.

## License

Made by Mish for Hack Club.

Available under the MIT License - see [LICENSE](LICENSE) for details.
