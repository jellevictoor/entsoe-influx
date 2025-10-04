#!/usr/bin/env python3
"""
ENTSO-E to InfluxDB Importer
Fetches electricity price data from ENTSO-E API and stores it in InfluxDB.
"""

from datetime import timedelta
from entsoe import EntsoePandasClient
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import typer

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
        print(f"Error fetching prices: {e}")
        return None


def write_to_influxdb(
    prices, country_code, influx_url, influx_token, influx_org, influx_bucket
):
    """Write price data to InfluxDB."""
    # Initialize InfluxDB client
    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    try:
        points = []
        for timestamp, price in prices.items():
            # Create a point for each price entry
            point = (
                Point("electricity_price")
                .tag("country", country_code)
                .tag("price_type", "day_ahead")
                .field("price_eur_mwh", float(price))
                .time(timestamp)
            )
            points.append(point)

        # Write all points to InfluxDB
        write_api.write(bucket=influx_bucket, org=influx_org, record=points)
        print(f"Successfully wrote {len(points)} data points to InfluxDB")

    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")
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
):
    """Main function to fetch and import ENTSO-E prices."""
    # Initialize ENTSO-E client
    entsoe_client = EntsoePandasClient(api_key=entsoe_api_key)

    # Define time range (last 7 days as example)
    end = pd.Timestamp.now(tz="UTC")
    start = end - timedelta(days=7)

    print(f"Fetching day-ahead prices for {country_code}")
    print(f"Time range: {start} to {end}")

    # Fetch prices
    prices = fetch_day_ahead_prices(entsoe_client, country_code, start, end)

    if prices is not None and not prices.empty:
        print(f"Fetched {len(prices)} price points")

        # Write to InfluxDB
        write_to_influxdb(
            prices, country_code, influx_url, influx_token, influx_org, influx_bucket
        )
    else:
        print("No data fetched")


if __name__ == "__main__":
    app()
