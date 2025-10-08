# ENTSO-E to InfluxDB Importer with evcc API

Fetches day-ahead electricity price data from the ENTSO-E Transparency Platform API, stores it in InfluxDB, and exposes it via a REST API in evcc-compatible format.

## Features

- Fetch day-ahead electricity prices from ENTSO-E API
- Store data in InfluxDB with country and price type tags
- **REST API endpoint for evcc integration**
- Support for all ENTSO-E country codes and 15-minute intervals
- Automatic tax calculation
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
# Pull importer image from GitHub Container Registry
docker pull ghcr.io/jellevictoor/entsoe-influx:latest

# Pull API image from GitHub Container Registry
docker pull ghcr.io/jellevictoor/entsoe-influx-api:latest

# Run importer once
docker run --rm \
  -e ENTSOE_API_KEY=your-api-key \
  -e INFLUX_URL=http://influxdb:8086 \
  -e INFLUX_TOKEN=your-token \
  -e INFLUX_ORG=your-org \
  ghcr.io/jellevictoor/entsoe-influx:latest \
  --country-code BE

# Run API service
docker run -d \
  -p 8000:8000 \
  -e INFLUX_URL=http://influxdb:8086 \
  -e INFLUX_TOKEN=your-token \
  -e INFLUX_ORG=your-org \
  -e TAX=0.06 \
  ghcr.io/jellevictoor/entsoe-influx-api:latest
```

### Docker Compose (Scheduled + API)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```bash
   ENTSOE_API_KEY=your-api-key
   COUNTRY_CODE=BE
   INFLUX_URL=http://influxdb:8086
   INFLUX_TOKEN=your-token
   INFLUX_ORG=your-org
   INFLUX_BUCKET=energy_prices
   TAX=0.06  # Optional: Tax to apply (e.g., 0.06 = 6%)
   ```

3. Start all services:
   ```bash
   docker compose up -d
   ```

This starts:
- **API service** on port 8000 (exposing prices for evcc)
- **Scheduler** that runs the importer daily at 2 PM (14:00)

To run the importer manually:

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

## evcc Integration

The API service exposes electricity prices in a format compatible with evcc's custom tariff forecast.

### evcc Configuration

Replace your ENTSO-E template configuration with this custom source:

```yaml
tariffs:
  grid:
    type: custom
    forecast:
      source: http
      uri: http://localhost:8000/prices  # Or your server's IP/hostname
  feedin:
    type: fixed
    price: 0.020  # EUR/kWh
```

**Note:** No `jq` transformation needed! The API returns data in the exact format evcc expects.

### API Endpoints

#### GET /prices

Returns electricity price forecast in evcc format.

**Query Parameters:**
- `country` (optional) - Filter by country code (e.g., `BE`, `NL`)
- `tax` (optional) - Override tax rate (e.g., `0.06` for 6%)

**Examples:**
```bash
# Get all prices with default tax from environment
curl http://localhost:8000/prices

# Get prices for Belgium with 6% tax
curl http://localhost:8000/prices?country=BE&tax=0.06
```

**Response Format:**
```json
[
  {
    "start": "2025-01-01T00:00:00Z",
    "end": "2025-01-01T00:15:00Z",
    "value": 0.25
  },
  {
    "start": "2025-01-01T00:15:00Z",
    "end": "2025-01-01T00:30:00Z",
    "value": 0.265
  }
]
```

- Prices are in **EUR/kWh** (euros per kilowatt-hour)
- Covers **48 hours past** and **48 hours future**
- Tax is automatically applied based on `TAX` environment variable or query parameter
- Supports **15-minute intervals** (or any interval in your InfluxDB data)

#### GET /health

Health check endpoint for monitoring.

### How It Works

1. The importer fetches day-ahead prices from ENTSO-E daily at 14:00 UTC
2. Prices are stored in InfluxDB with timestamps
3. The API queries InfluxDB and formats prices for evcc
4. evcc polls the API hourly to get updated forecasts

### Benefits over ENTSO-E Template

- ✅ **Offline access** - No dependency on ENTSO-E API availability
- ✅ **Historical data** - Access to past prices stored in InfluxDB
- ✅ **Flexible tax handling** - Configure tax via environment or per-request
- ✅ **Custom intervals** - Supports 15-minute or hourly data
- ✅ **Single source** - Same data for evcc and other applications (Grafana, etc.)

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