#!/usr/bin/env python3
"""Generate synthetic banking data and replace sample BigQuery tables."""

import argparse
import io
import json
import random
import re
import sys
from datetime import date, timedelta

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

AS_OF_DATE = date(2026, 1, 1)
TABLE_SCHEMAS = {
    "debtors": [
        ("debtor_id", "STRING"),
        ("annual_income", "NUMERIC"),
        ("monthly_money_at_disposal", "NUMERIC"),
        ("employment_status", "STRING"),
    ],
    "arrangements": [
        ("ar_id", "STRING"),
        ("debtor_id", "STRING"),
        ("origination_date", "DATE"),
        ("maturity_date", "DATE"),
        ("status", "STRING"),
    ],
    "balance_sheet": [
        ("ar_id", "STRING"),
        ("balance_type", "STRING"),
        ("balance_amount", "NUMERIC"),
        ("currency", "STRING"),
        ("as_of_date", "DATE"),
    ],
    "properties": [
        ("property_id", "STRING"),
        ("property_value", "NUMERIC"),
        ("currency", "STRING"),
    ],
    "deeds": [
        ("deed_id", "STRING"),
        ("property_id", "STRING"),
    ],
    "collaterals": [
        ("collateral_id", "STRING"),
        ("deed_id", "STRING"),
        ("ar_id", "STRING"),
        ("property_id", "STRING"),
        ("encumbrance", "NUMERIC"),
        ("currency", "STRING"),
    ],
    "defaults": [
        ("ar_id", "STRING"),
        ("default_date", "DATE"),
    ],
}


def identifier(prefix, number):
    return f"{prefix}-{number:06d}"


def generate_data(count, seed):
    """Return deterministic, mutually consistent synthetic table rows."""
    rng = random.Random(seed)
    debtor_count = max(1, count * 3 // 4)
    deed_count = max(2, count * 3 // 5)
    property_count = max(1, count // 2)
    tables = {name: [] for name in TABLE_SCHEMAS}

    for i in range(1, debtor_count + 1):
        income = rng.randrange(20000, 150001)
        tables["debtors"].append({
            "debtor_id": identifier("DEB", i),
            "annual_income": str(income),
            "monthly_money_at_disposal": str(rng.randrange(200, max(201, income // 24))),
            "employment_status": rng.choice(["EMPLOYED", "SELF_EMPLOYED", "RETIRED", "UNEMPLOYED"]),
        })

    property_values = {}
    for i in range(1, property_count + 1):
        property_id = identifier("PROP", i)
        property_values[property_id] = rng.randrange(100000, 1000001)
        tables["properties"].append({
            "property_id": property_id,
            "property_value": str(property_values[property_id]),
            "currency": "EUR",
        })

    deed_properties = {}
    for i in range(1, deed_count + 1):
        deed_id = identifier("DEED", i)
        property_id = identifier("PROP", (i - 1) % property_count + 1)
        deed_properties[deed_id] = property_id
        tables["deeds"].append({"deed_id": deed_id, "property_id": property_id})

    for i in range(1, count + 1):
        ar_id = identifier("AR", i)
        origination = date(2012, 1, 1) + timedelta(days=rng.randrange(4748))
        maturity = origination + timedelta(days=365 * rng.choice([10, 15, 20]))
        is_default = maturity > AS_OF_DATE and i % 12 == 0
        status = "DEFAULTED" if is_default else "MATURED" if maturity <= AS_OF_DATE else "ACTIVE"
        tables["arrangements"].append({
            "ar_id": ar_id,
            "debtor_id": identifier("DEB", rng.randrange(1, debtor_count + 1)),
            "origination_date": origination.isoformat(),
            "maturity_date": maturity.isoformat(),
            "status": status,
        })
        if is_default:
            elapsed_days = (AS_OF_DATE - origination).days
            default_date = origination + timedelta(days=rng.randrange(1, elapsed_days + 1))
            tables["defaults"].append({"ar_id": ar_id, "default_date": default_date.isoformat()})

        principal = 0 if status == "MATURED" else rng.randrange(10000, 500001)
        for balance_type, amount in (
            ("PRINCIPAL", principal),
            ("ACCRUED_INTEREST", 0 if principal == 0 else rng.randrange(0, principal // 20 + 1)),
        ):
            tables["balance_sheet"].append({
                "ar_id": ar_id,
                "balance_type": balance_type,
                "balance_amount": str(amount),
                "currency": "EUR",
                "as_of_date": AS_OF_DATE.isoformat(),
            })

        deed_numbers = [(i - 1) % deed_count + 1]
        if i % 5 == 0:
            deed_numbers.append((i - 1 + deed_count // 2) % deed_count + 1)
        for deed_number in deed_numbers:
            deed_id = identifier("DEED", deed_number)
            property_id = deed_properties[deed_id]
            tables["collaterals"].append({
                "collateral_id": identifier("COL", len(tables["collaterals"]) + 1),
                "deed_id": deed_id,
                "ar_id": ar_id,
                "property_id": property_id,
                "encumbrance": str(property_values[property_id] // 50),
                "currency": "EUR",
            })

    return tables


def load_data(project, dataset, location, count, seed):
    tables = generate_data(count, seed)
    client = bigquery.Client(project=project, location=location)
    dataset_ref = bigquery.Dataset(f"{project}.{dataset}")
    dataset_ref.location = location
    actual_dataset = client.create_dataset(dataset_ref, exists_ok=True)
    if actual_dataset.location.lower() != location.lower():
        raise ValueError(
            f"Dataset {project}.{dataset} is in {actual_dataset.location}, not {location}."
        )

    for name, rows in tables.items():
        data = io.BytesIO(
            "".join(json.dumps(row) + "\n" for row in rows).encode("utf-8")
        )
        job_config = bigquery.LoadJobConfig(
            schema=[
                bigquery.SchemaField(field, field_type, mode="REQUIRED")
                for field, field_type in TABLE_SCHEMAS[name]
            ],
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        table_id = f"{project}.{dataset}.{name}"
        print(f"Replacing {table_id} with {len(rows)} rows", flush=True)
        client.load_table_from_file(data, table_id, job_config=job_config).result()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Shared Google Cloud project ID")
    parser.add_argument("--dataset", default="banking_sample", help="BigQuery dataset ID (default: banking_sample)")
    parser.add_argument("--location", default="EU", help="BigQuery dataset location (default: EU)")
    parser.add_argument("--count", type=int, default=10000, help="Number of arrangements (default: 10000)")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed (default: 2026)")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project):
        parser.error("--project must be a valid Google Cloud project ID")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,1023}", args.dataset):
        parser.error("--dataset must be a valid BigQuery dataset ID")
    if not re.fullmatch(r"[A-Za-z0-9-]+", args.location):
        parser.error("--location must be a BigQuery location name")
    if args.count < 2:
        parser.error("--count must be at least 2")

    try:
        load_data(args.project, args.dataset, args.location, args.count, args.seed)
    except (GoogleAPIError, DefaultCredentialsError, ValueError) as error:
        print(f"Error: {error}. Earlier tables may already have been replaced.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
