#!/usr/bin/env python3
"""
ENTSO-E to InfluxDB Importer
Fetches electricity price data from ENTSO-E API and stores it in InfluxDB.
"""

import logging
from datetime import timedelta
from entsoe import EntsoePandasClient
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import typer

logger = logging.getLogger(__name__)

# ENTSO-E country codes (examples)
# Full list: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
COUNTRY_CODE = "BE"

app = typer.Typer()


def fetch_day_ahead_prices(client, country_code, start, end):
    """Fetch day-ahead prices from ENTSO-E API."""
    try:
        prices = client.query_day_ahead_prices(country_code, start=start, end=end)
        return prices
    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)
        return None


def write_to_influxdb(
    prices, country_code, influx_url, influx_token, influx_org, influx_bucket, tax=0.0
):
    """Write price data to InfluxDB."""
    # Initialize InfluxDB client
    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    try:
        points = []
        for timestamp, price in prices.items():
            price_mwh = float(price)
            price_kwh = price_mwh / 1000  # Convert EUR/MWh to EUR/kWh
            price_kwh_with_tax = price_kwh * (1 + tax)  # Apply tax

            # Create a point for each price entry with multiple fields
            point = (
                Point("electricity_price")
                .tag("country", country_code)
                .tag("price_type", "day_ahead")
                .field("price_eur_mwh", price_mwh)
                .field("price_eur_kwh", price_kwh)
                .field("price_eur_kwh_with_tax", price_kwh_with_tax)
                .time(timestamp)
            )
            points.append(point)

        # Write all points to InfluxDB
        write_api.write(bucket=influx_bucket, org=influx_org, record=points)
        logger.info(f"Successfully wrote {len(points)} data points to InfluxDB")

    except Exception as e:
        logger.error(f"Error writing to InfluxDB: {e}", exc_info=True)
    finally:
        client.close()


@app.command()
def main(
    entsoe_api_key: str = typer.Option(
        ..., envvar="ENTSOE_API_KEY", help="ENTSO-E API key"
    ),
    influx_url: str = typer.Option(
        "http://localhost:8086", envvar="INFLUX_URL", help="InfluxDB URL"
    ),
    influx_token: str = typer.Option(
        ..., envvar="INFLUX_TOKEN", help="InfluxDB authentication token"
    ),
    influx_org: str = typer.Option(
        ..., envvar="INFLUX_ORG", help="InfluxDB organization"
    ),
    influx_bucket: str = typer.Option(
        "energy_prices", envvar="INFLUX_BUCKET", help="InfluxDB bucket name"
    ),
    country_code: str = typer.Option(
        "BE", "--country-code", help="ENTSO-E country code (e.g., BE, DE_LU, NL)"
    ),
    tax: float = typer.Option(
        0.0, envvar="TAX", help="Tax rate to apply (e.g., 0.06 for 6%)"
    ),
):
    """Main function to fetch and import ENTSO-E prices."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting ENTSO-E to InfluxDB import")

    # Initialize ENTSO-E client
    entsoe_client = EntsoePandasClient(api_key=entsoe_api_key)

    # Define time range (last 7 days + next 2 days to include day-ahead forecasts)
    start = pd.Timestamp.now(tz="UTC") - timedelta(days=7)
    end = pd.Timestamp.now(tz="UTC") + timedelta(days=2)

    logger.info(f"Fetching day-ahead prices for {country_code}")
    logger.info(f"Time range: {start} to {end}")

    # Fetch prices
    prices = fetch_day_ahead_prices(entsoe_client, country_code, start, end)

    if prices is not None and not prices.empty:
        logger.info(f"Fetched {len(prices)} price points")

        # Write to InfluxDB
        write_to_influxdb(
            prices,
            country_code,
            influx_url,
            influx_token,
            influx_org,
            influx_bucket,
            tax,
        )
    else:
        logger.warning("No data fetched")

    logger.info("Import completed")


if __name__ == "__main__":
    app()
