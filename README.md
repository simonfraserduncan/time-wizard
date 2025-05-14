# Timezone Wizard

A Model Context Protocol (MCP) server providing advanced timezone conversions and calendar utilities for LLMs.

## Features

- Get current time in specified timezone
- Convert time between timezones
- More features coming soon...

## Installation

```bash
pip install timezone-wizard
```

## Usage

To run the server with default settings (HTTP server on 0.0.0.0:8000):

```bash
timezone-wizard
```

### Configuration options:

You can customize the server behavior with these options:

```bash
# Override local timezone
timezone-wizard --local-timezone America/New_York

# Specify host and port
timezone-wizard --host 127.0.0.1 --port 3000

# Combine options
timezone-wizard --local-timezone Europe/London --host 127.0.0.1 --port 3000
```

## Connecting to the server

The server provides an HTTP endpoint at `/mcp` for Model Context Protocol clients to connect.

Example URL: `http://localhost:8000/mcp` 