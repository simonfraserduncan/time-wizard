# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS uv

WORKDIR /app

# Enable bytecode compilation & copy link mode
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Add all project files first (respects .dockerignore)
ADD . /app

# Install the project and its dependencies using the lockfile
RUN --mount=type=cache,target=/root/.cache/uv \
    bash -c "uv venv && source .venv/bin/activate && uv pip install ."

FROM python:3.12-slim-bookworm

WORKDIR /app
 
COPY --from=uv /root/.local /root/.local
COPY --from=uv --chown=app:app /app/.venv /app/.venv

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# when running the container, add --db-path and a bind mount to the host's db file
ENTRYPOINT ["timezone-wizard"]
