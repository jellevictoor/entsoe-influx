#!/usr/bin/env python3
"""
ENTSO-E to InfluxDB Importer
Fetches electricity price data from ENTSO-E API and stores it in InfluxDB.
"""

import logging
from datetime import timedelta

from dotenv import load_dotenv
from entsoe import EntsoePandasClient
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import typer

load_dotenv()
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


@app.command()
def backfill(
    days: int = typer.Option(
        365, "--days", help="Number of days to backfill (default: 365 for one year)"
    ),
    chunk_days: int = typer.Option(
        30, "--chunk-days", help="Number of days to fetch per API request (default: 30)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be fetched without writing to database",
    ),
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
    """Backfill historical electricity price data from ENTSO-E API."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if dry_run:
        logger.info("🔍 DRY RUN MODE - No data will be written to database")

    logger.info(f"Starting historical data backfill for {country_code}")
    logger.info(f"Backfill period: {days} days")
    logger.info(f"Chunk size: {chunk_days} days per request")

    # Initialize ENTSO-E client
    entsoe_client = EntsoePandasClient(api_key=entsoe_api_key)

    # Calculate time ranges
    end_time = pd.Timestamp.now(tz="UTC")
    start_time = end_time - timedelta(days=days)

    logger.info(f"Time range: {start_time} to {end_time}")

    # Calculate chunks
    current_start = start_time
    chunk_count = 0
    total_points = 0
    failed_chunks = []

    while current_start < end_time:
        chunk_count += 1
        current_end = min(current_start + timedelta(days=chunk_days), end_time)

        logger.info(
            f"\n📦 Chunk {chunk_count}: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}"
        )

        if dry_run:
            logger.info(
                "   Would fetch data for this period (skipping in dry-run mode)"
            )
            current_start = current_end
            continue

        # Fetch prices for this chunk
        try:
            prices = fetch_day_ahead_prices(
                entsoe_client, country_code, current_start, current_end
            )

            if prices is not None and not prices.empty:
                logger.info(f"   ✓ Fetched {len(prices)} price points")

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
                total_points += len(prices)
            else:
                logger.warning("   ⚠ No data available for this period")
                failed_chunks.append((current_start, current_end))

        except Exception as e:
            logger.error(f"   ✗ Error processing chunk: {e}")
            failed_chunks.append((current_start, current_end))

        # Move to next chunk
        current_start = current_end

    # Summary
    logger.info("\n" + "=" * 60)
    if dry_run:
        logger.info("DRY RUN SUMMARY")
        logger.info(f"Would fetch {chunk_count} chunks covering {days} days")
        logger.info("Run without --dry-run to actually fetch and store the data")
    else:
        logger.info("BACKFILL SUMMARY")
        logger.info(f"Processed {chunk_count} chunks")
        logger.info(f"Total data points written: {total_points}")

        if failed_chunks:
            logger.warning(f"\n⚠ {len(failed_chunks)} chunks failed:")
            for start, end in failed_chunks:
                logger.warning(
                    f"   - {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                )
        else:
            logger.info("✓ All chunks processed successfully!")

    logger.info("=" * 60)
    logger.info("Backfill completed")


if __name__ == "__main__":
    app()
