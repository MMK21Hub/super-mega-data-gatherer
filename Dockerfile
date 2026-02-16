FROM ghcr.io/astral-sh/uv:debian-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY .python-version .
COPY uv.lock .
RUN uv sync --locked
COPY *.py .

# Configure
EXPOSE 8000
ENV PORT=8000
ENV HOST=0.0.0.0

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["uv", "run", "main.py"]
