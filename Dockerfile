# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS uv

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Copy project files first
COPY pyproject.toml .

# Install dependencies without using the frozen lockfile
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps -e .

# Then, add the rest of the project source code
ADD . /app

FROM python:3.12-slim-bookworm

WORKDIR /app

# Create a non-root user
RUN groupadd -r app && useradd -r -g app app

COPY --from=uv /root/.local /root/.local
COPY --from=uv /app /app

# Place executables in the environment at the front of the path
ENV PATH="/root/.local/bin:$PATH"

# Set proper ownership
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Launch timezone-wizard when the container starts
ENTRYPOINT ["timezone-wizard"] 