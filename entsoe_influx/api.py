#!/usr/bin/env python3
"""
ENTSO-E Price API for evcc
Exposes electricity prices from InfluxDB in evcc-compatible format.
"""

import logging
import os
from typing import List

from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ENTSO-E Price API",
    description="Provides electricity prices in evcc-compatible format",
    version="0.1.0",
)


class PriceEntry(BaseModel):
    """Price entry model for evcc."""

    start: str
    end: str
    value: float


def get_influx_client():
    """Create and return an InfluxDB client."""
    influx_url = os.getenv("INFLUX_URL", "http://localhost:8086")
    influx_token = os.getenv("INFLUX_TOKEN")
    influx_org = os.getenv("INFLUX_ORG")

    if not influx_token or not influx_org:
        raise ValueError(
            "INFLUX_TOKEN and INFLUX_ORG environment variables are required"
        )

    return InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)


def query_prices(country_code: str = None, tax: float = 0.0) -> List[PriceEntry]:
    """Query prices from InfluxDB and format for evcc."""
    influx_bucket = os.getenv("INFLUX_BUCKET", "energy_prices")
    influx_org = os.getenv("INFLUX_ORG")

    client = get_influx_client()
    query_api = client.query_api()

    # Build the query - get all prices from the last 48 hours and next 48 hours
    country_filter = (
        f'|> filter(fn: (r) => r["country"] == "{country_code}")'
        if country_code
        else ""
    )

    query = f'''
    from(bucket: "{influx_bucket}")
        |> range(start: -48h, stop: 48h)
        |> filter(fn: (r) => r["_measurement"] == "electricity_price")
        {country_filter}
        |> filter(fn: (r) => r["_field"] == "price_eur_mwh")
        |> sort(columns: ["_time"])
    '''

    try:
        result = query_api.query(org=influx_org, query=query)

        prices = []
        records_list = []

        # Collect all records first
        for table in result:
            for record in table.records:
                records_list.append(record)

        # Process records and calculate intervals
        for i, record in enumerate(records_list):
            # Get the timestamp and price
            timestamp = record.get_time()
            price_mwh = record.get_value()

            # Convert price from EUR/MWh to EUR/kWh (divide by 1000)
            # and from EUR/kWh to ct/kWh (multiply by 100)
            # Net result: divide by 10
            price_ct_kwh = price_mwh / 10

            # Apply tax (tax is a multiplier, e.g., 0.06 = 6%)
            price_with_tax = price_ct_kwh * (1 + tax)

            # Format the time period
            start_time = timestamp.isoformat().replace("+00:00", "Z")

            # Calculate end time based on next record, or default to 15 minutes
            if i + 1 < len(records_list):
                end_timestamp = records_list[i + 1].get_time()
            else:
                # Default to 15 minutes for the last record
                from datetime import timedelta

                end_timestamp = timestamp + timedelta(minutes=15)

            end_time = end_timestamp.isoformat().replace("+00:00", "Z")

            prices.append(
                PriceEntry(
                    start=start_time, end=end_time, value=round(price_with_tax, 2)
                )
            )

        return prices

    except Exception as e:
        logger.error(f"Error querying InfluxDB: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error querying prices: {str(e)}")
    finally:
        client.close()


@app.get("/prices", response_model=List[PriceEntry])
async def get_prices(country: str = None, tax: float = None):
    """
    Get electricity prices in evcc format.

    Args:
        country: Optional country code filter (e.g., BE, DE_LU, NL)
        tax: Optional tax multiplier (e.g., 0.06 for 6% tax). Can also be set via TAX env variable.

    Returns:
        List of price entries with start/end times and values
    """
    # Use query param tax, or fall back to environment variable, or default to 0
    if tax is None:
        tax = float(os.getenv("TAX", "0.0"))

    prices = query_prices(country, tax)
    return prices


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    uvicorn.run(app, host="0.0.0.0", port=8000)
