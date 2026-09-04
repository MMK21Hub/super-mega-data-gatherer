FROM ghcr.io/astral-sh/uv:debian-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY .python-version .
COPY uv.lock .
RUN uv sync --locked
COPY *.py .
COPY config.yaml .

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["uv", "run", "main.py"]
