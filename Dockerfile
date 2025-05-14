FROM python:3.12-slim-bookworm

WORKDIR /app

# Create a non-root user
RUN groupadd -r app && useradd -r -g app app

# Install the app and dependencies
COPY . /app/
RUN pip install -e .

# Set proper ownership
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Launch timezone-wizard when the container starts
ENTRYPOINT ["timezone-wizard"] 