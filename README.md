# ENTSO-E to InfluxDB Importer

Fetches day-ahead electricity price data from the ENTSO-E Transparency Platform API and stores it in InfluxDB.

## Features

- Fetch day-ahead electricity prices from ENTSO-E API
- Store data in InfluxDB with country and price type tags
- Support for all ENTSO-E country codes
- CLI interface with environment variable support
- Docker support with multi-architecture builds (amd64, arm64)
- Automated daily imports via Docker Compose with scheduler

## Installation

### Using uv (recommended)

```bash
uv sync
```

### Using pip

```bash
pip install -r requirements.txt
```

## Usage

### Command Line

```bash
# Using environment variables
export ENTSOE_API_KEY="your-api-key"
export INFLUX_TOKEN="your-token"
export INFLUX_ORG="your-org"

uv run python -m entsoe_influx.main

# Using CLI arguments
uv run python -m entsoe_influx.main \
  --entsoe-api-key your-api-key \
  --influx-url http://localhost:8086 \
  --influx-token your-token \
  --influx-org your-org \
  --influx-bucket energy_prices \
  --country-code BE
```

### Docker

```bash
# Pull from GitHub Container Registry
docker pull ghcr.io/jellevictoor/entsoe-influx:latest

# Run once
docker run --rm \
  -e ENTSOE_API_KEY=your-api-key \
  -e INFLUX_URL=http://influxdb:8086 \
  -e INFLUX_TOKEN=your-token \
  -e INFLUX_ORG=your-org \
  ghcr.io/jellevictoor/entsoe-influx:latest \
  --country-code BE
```

### Docker Compose (Scheduled)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials

3. Start the scheduler:
   ```bash
   docker compose up -d scheduler
   ```

The importer will run daily at 2 PM (14:00). To run manually:

```bash
docker compose run --rm entsoe-influx
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENTSOE_API_KEY` | Yes | - | Your ENTSO-E API key |
| `INFLUX_URL` | No | `http://localhost:8086` | InfluxDB server URL |
| `INFLUX_TOKEN` | Yes | - | InfluxDB authentication token |
| `INFLUX_ORG` | Yes | - | InfluxDB organization |
| `INFLUX_BUCKET` | No | `energy_prices` | InfluxDB bucket name |

### CLI Options

```bash
uv run python -m entsoe_influx.main --help
```

- `--entsoe-api-key`: ENTSO-E API key
- `--influx-url`: InfluxDB URL
- `--influx-token`: InfluxDB authentication token
- `--influx-org`: InfluxDB organization
- `--influx-bucket`: InfluxDB bucket name
- `--country-code`: ENTSO-E country code (e.g., BE, DE_LU, NL)

### Country Codes

Common ENTSO-E country codes:
- `BE` - Belgium
- `NL` - Netherlands
- `DE_LU` - Germany-Luxembourg
- `FR` - France
- `GB` - Great Britain

Full list available at: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html

## Getting an ENTSO-E API Key

1. Register at https://transparency.entsoe.eu/
2. Send an email to transparency@entsoe.eu with "Restful API access" in the subject
3. You'll receive your API key via email

## Development

```bash
# Install dependencies including dev tools
uv sync

# Run linter
uv run ruff check

# Format code
uv run ruff format
```

## License

[Add your license here]