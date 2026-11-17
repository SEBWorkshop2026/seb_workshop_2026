#!/usr/bin/env python3
"""Generate synthetic banking source systems in BigQuery and Cloud Storage."""

import argparse
import csv
import io
import json
import math
import random
import re
import sys
from datetime import date, timedelta

from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery, storage

CURRENCY = "EUR"
SNAPSHOTS = [date(year, month, 1) for year in (2024, 2025) for month in range(1, 13)]
SNAPSHOTS.append(date(2026, 1, 1))

TABLE_SCHEMAS = {
    "debtor_info": [
        ("reporting_date", "DATE"),
        ("debtor_identifier", "STRING"), ("age", "INTEGER"), ("sex", "STRING"),
        ("education", "INTEGER"), ("politically_exposed", "BOOLEAN"),
        ("underage_children_count", "INTEGER"), ("family_status", "STRING"),
        ("residence_region", "STRING"),
    ],
    "arrangement_account_info": [
        ("reporting_date", "DATE"),
        ("loan_id", "STRING"), ("reason_for_loan", "STRING"), ("type_of_loan", "STRING"),
        ("initial_credit_limit", "NUMERIC"), ("currency", "STRING"), ("origination_date", "INTEGER"),
        ("maturity_date", "INTEGER"), ("debtor_id", "STRING"), ("co_debtor_id", "STRING"),
    ],
    "defaults": [("reporting_date", "DATE"), ("loan_id", "STRING"), ("default_date", "DATE")],
}

CSV_FIELDS = {
    "debtor_financial": [
        "reporting_date", "debtor_identifier", "income", "funds_available", "currency",
        "credit_rating", "household_income", "employment_industry", "proposed_risk_class",
    ],
    "arrangement_balance": [
        "reporting_date", "loan_id", "loan_status", "original_principal_balance",
        "current_principal_balance", "next_payment_due", "currency", "interest_rate", "interest_type",
        "inv_due_date",
    ],
    "collateral": [
        "reporting_date", "collateral_id", "loan_id", "property_id", "property_value", "currency",
        "collateral_type", "loan_to_value_ratio",
    ],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Google Cloud project ID")
    parser.add_argument("--bucket", required=True, help="Existing Cloud Storage bucket for CSV source files")
    parser.add_argument("--prefix", default="banking_sample", help="Object prefix in the bucket")
    parser.add_argument("--dataset", default="banking_sample", help="BigQuery dataset ID")
    parser.add_argument("--location", default="EU", help="BigQuery dataset location")
    parser.add_argument("--count", type=int, default=10000, help="Number of loans")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed")
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
        load_data(args.project, args.dataset, args.location, args.bucket, args.prefix, args.count, args.seed)
    except (GoogleAPIError, DefaultCredentialsError, ValueError) as error:
        print(f"Error: {error}. Earlier tables or objects may already have been replaced.", file=sys.stderr)
        return 1
    return 0


def load_data(project, dataset, location, bucket, prefix, count, seed):
    tables, snapshots = generate_data(count, seed)
    client = bigquery.Client(project=project, location=location)
    storage_client = storage.Client(project=project)
    # Check the bucket exists and is accessible before replacing any tables.
    bucket_ref = storage_client.get_bucket(bucket)
    dataset_ref = bigquery.Dataset(f"{project}.{dataset}")
    dataset_ref.location = location
    actual_dataset = client.create_dataset(dataset_ref, exists_ok=True)
    if actual_dataset.location.lower() != location.lower():
        raise ValueError(f"Dataset {project}.{dataset} is in {actual_dataset.location}, not {location}.")

    for name in TABLE_SCHEMAS:
        table_id = f"{project}.{dataset}.{name}"
        try:
            existing = client.get_table(table_id)
        except NotFound:
            continue
        partitioning = existing.time_partitioning
        if partitioning is None or partitioning.field != "reporting_date" or partitioning.type_ != "MONTH":
            raise ValueError(
                f"Table {table_id} is not monthly-partitioned by reporting_date. "
                "Use a new dataset or remove the incompatible table before rerunning."
            )

    for name, rows in tables.items():
        data = io.BytesIO("".join(json.dumps(row) + "\n" for row in rows).encode("utf-8"))
        job_config = bigquery.LoadJobConfig(
            schema=[
                bigquery.SchemaField(field, field_type, mode="NULLABLE" if field == "co_debtor_id" else "REQUIRED")
                for field, field_type in TABLE_SCHEMAS[name]
            ],
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            time_partitioning=bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.MONTH, field="reporting_date"
            ),
        )
        table_id = f"{project}.{dataset}.{name}"
        print(f"Replacing {table_id} with {len(rows)} rows", flush=True)
        client.load_table_from_file(data, table_id, job_config=job_config).result()

    for day, systems in snapshots.items():
        for name, rows in systems.items():
            path = "/".join(part for part in (prefix.strip("/"), name, f"{day.isoformat()}.csv") if part)
            print(f"Replacing gs://{bucket}/{path} with {len(rows)} rows", flush=True)
            bucket_ref.blob(path).upload_from_string(csv_data(rows, CSV_FIELDS[name]), content_type="text/csv")


def generate_data(count, seed):
    """Generate a 24-month observation window and its initial snapshot."""
    rng = random.Random(seed)
    tables = {name: [] for name in TABLE_SCHEMAS}
    snapshots = {day: {name: [] for name in CSV_FIELDS} for day in SNAPSHOTS}

    def make_debtor(number, household=None):
        age_mean = household["age"] if household else 37.5
        age_stddev = 5 if household else 8
        age = round(rng.gauss(age_mean, age_stddev))
        while not 25 <= age <= 65:
            age = round(rng.gauss(age_mean, age_stddev))

        if age < 30:
            family_weights = [67.9, 28, 4, 0.1]
            child_probability = 0.12
        elif age < 45:
            family_weights = [42, 49, 8, 1]
            child_probability = 0.30
        else:
            family_weights = [24, 56, 16, 4]
            child_probability = 0.16 if age < 55 else 0.03

        family_status = rng.choices(
            ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED"], family_weights
        )[0]
        if household:
            region = household["residence_region"]
            children = household["underage_children_count"]
            if household["family_status"] == "MARRIED":
                family_status = "MARRIED"
        else:
            region = rng.choices(
                ["ALYTUS", "KAUNAS", "KLAIPEDA", "MARIJAMPOLE", "PANEVEZYS",
                 "SIAULIAI", "TAURAGE", "TELSIAI", "UTENA", "VILNIUS"],
                [134201, 585480, 339972, 134668, 209071,
                 266960, 90578, 130918, 126326, 868341],
            )[0]
            children = (
                rng.choices([1, 2, 3], [184.2, 116.6, 25.1])[0]
                if rng.random() < child_probability else 0
            )
        debtor = {
            "debtor_identifier": identifier("DEB", number),
            "age": age,
            "sex": rng.choices(["FEMALE", "MALE"], [52.7, 47.3])[0],
            "education": rng.choices([1, 2, 3, 4], [5.6, 46.8, 31.7, 15.9])[0],
            "politically_exposed": rng.random() < 0.01,
            "underage_children_count": children,
            "family_status": family_status,
            "residence_region": region,
        }
        income = round(min(7000, max(600, rng.lognormvariate(math.log(1260), 0.4))))
        financial = {
            "debtor_identifier": debtor["debtor_identifier"],
            "income": income,
            "credit_rating": rng.choices([1, 2, 3, 4, 5], [30, 35, 22, 10, 3])[0],
            "employment_industry": rng.choices(
                ["FINANCE_IT", "SERVICES", "MANUFACTURING", "AGRICULTURE", "OTHER_INDUSTRY"],
                [92.9, 856.9, 227.1, 66.4, 141.4],
            )[0],
        }
        financial["proposed_risk_class"] = max(
            1, min(5, financial["credit_rating"] + rng.choice([-1, 0, 0, 0, 1]))
        )
        return debtor, financial

    next_co_debtor = count + 1
    for i in range(1, count + 1):
        debtor, financial = make_debtor(i)
        borrowers = [(debtor, financial)]
        if rng.random() < 0.35:
            borrowers.append(make_debtor(next_co_debtor, debtor))
            next_co_debtor += 1
        household_income = sum(person[1]["income"] for person in borrowers)
        co_debtor = borrowers[1][0]["debtor_identifier"] if len(borrowers) == 2 else None
        loan_id = identifier("LOAN", i)
        reason = rng.choices(["HOME", "INVESTMENT"], [90, 10])[0]
        interest_type = rng.choices(["FIXED", "VARIABLE"], [5, 95])[0]
        rate = round(min(6.5, max(2.5, rng.gauss(4.0, 0.6))), 2)
        term_years = rng.choices([15, 20, 25, 30], [10, 20, 30, 40])[0]
        origination = date(2020 + rng.randrange(4), 1 + rng.randrange(12), 1)
        maturity = date(origination.year + term_years, origination.month, 1)
        stressed_payment_per_euro = monthly_payment(1, max(rate, 5), term_years * 12)
        principal = round(min(300000, household_income * rng.uniform(0.15, 0.35) / stressed_payment_per_euro))
        payment = monthly_payment(principal, rate, term_years * 12)
        origination_ltv = (
            rng.uniform(0.50, 0.70) if reason == "INVESTMENT"
            else 0.50 + 0.35 * rng.betavariate(5, 1.3)
        )
        property_value = math.ceil(principal / origination_ltv)
        collateral_type = rng.choices(["APARTMENT", "HOUSE"], [59.5, 39.5])[0]
        initial_balance = remaining_principal(
            principal, payment, rate,
            (SNAPSHOTS[0].year - origination.year) * 12 + SNAPSHOTS[0].month - origination.month,
        )
        living_expenses = 700 + 250 * (len(borrowers) - 1) + 200 * debtor["underage_children_count"]
        funds = max(0, round(household_income - payment - living_expenses))
        dsti = payment / household_income

        # Illustrative two-year log-odds, not the marginal correlations in the CSV.
        score = (
            -4.4 + 0.45 * (financial["credit_rating"] - 2)
            + 0.45 * (financial["proposed_risk_class"] - 2)
            + 1.5 * (dsti - 0.25) / 0.15
            + 0.25 * (initial_balance / property_value - 0.70) / 0.15
            + 0.20 * (rate - 4.0) / 0.6
            - 0.10 * (debtor["education"] - 2.5)
            - 0.10 * (debtor["age"] - 45) / 15
            + 0.25 * (reason == "INVESTMENT")
        )
        probability = 1 / (1 + math.exp(-score))
        default_date = None
        if rng.random() < probability:
            start = date(2024, 4, 1)
            default_date = start + timedelta(days=rng.randrange((SNAPSHOTS[-1] - start).days))

        # Some borrowers cure arrears, so arrears do not deterministically reveal future default.
        cure_date = None
        if default_date is None and rng.random() < 0.10:
            start = date(2024, 3, 1)
            cure_date = start + timedelta(days=rng.randrange((SNAPSHOTS[-1] - start).days))
        account = {
            "loan_id": loan_id, "reason_for_loan": reason, "type_of_loan": "MORTGAGE",
            "initial_credit_limit": principal, "currency": CURRENCY, "origination_date": date_integer(origination),
            "maturity_date": date_integer(maturity), "debtor_id": debtor["debtor_identifier"],
            "co_debtor_id": co_debtor,
        }
        for day in SNAPSHOTS:
            defaulted = default_date is not None and default_date <= day
            reporting_date = day.isoformat()
            tables["arrangement_account_info"].append({"reporting_date": reporting_date, **account})
            if defaulted:
                tables["defaults"].append({
                    "reporting_date": reporting_date, "loan_id": loan_id,
                    "default_date": default_date.isoformat(),
                })
            due_date = day + timedelta(days=30)
            balance_day = day
            if default_date is not None and day >= default_date - timedelta(days=91):
                due_date = default_date - timedelta(days=91)
                balance_day = due_date
            elif cure_date is not None and cure_date - timedelta(days=60) <= day < cure_date:
                due_date = cure_date - timedelta(days=60)
                balance_day = due_date
            months_elapsed = (balance_day.year - origination.year) * 12 + balance_day.month - origination.month
            current = round(remaining_principal(principal, payment, rate, max(0, months_elapsed)), 2)
            for person_debtor, person_financial in borrowers:
                tables["debtor_info"].append({"reporting_date": reporting_date, **person_debtor})
                snapshots[day]["debtor_financial"].append({
                    "reporting_date": reporting_date, **person_financial,
                    "funds_available": funds, "household_income": household_income, "currency": CURRENCY,
                })
            snapshots[day]["arrangement_balance"].append({
                "reporting_date": reporting_date, "loan_id": loan_id,
                "loan_status": "DEFAULTED" if defaulted else "ACTIVE",
                "original_principal_balance": principal, "current_principal_balance": current,
                "next_payment_due": round(payment, 2), "currency": CURRENCY, "interest_rate": rate,
                "interest_type": interest_type, "inv_due_date": due_date.isoformat(),
            })
            snapshots[day]["collateral"].append({
                "reporting_date": reporting_date, "collateral_id": identifier("COL", i),
                "loan_id": loan_id, "property_id": identifier("PROP", i),
                "property_value": property_value, "currency": CURRENCY,
                "collateral_type": collateral_type, "loan_to_value_ratio": round(current / property_value, 4),
            })
    return tables, snapshots


def csv_data(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def identifier(prefix, number):
    return f"{prefix}-{number:06d}"


def monthly_payment(principal, annual_rate, months):
    monthly_rate = annual_rate / 1200
    return principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def remaining_principal(principal, payment, annual_rate, months_elapsed):
    monthly_rate = annual_rate / 1200
    growth = (1 + monthly_rate) ** months_elapsed
    return max(0, principal * growth - payment * (growth - 1) / monthly_rate)


def date_integer(value):
    return int(value.strftime("%Y%m%d"))


if __name__ == "__main__":
    sys.exit(main())
