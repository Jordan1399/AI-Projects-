#!/usr/bin/env python3
"""
Clean and standardize the four Airline Loyalty CSV files for MySQL.

Outputs:
  customer_loyalty_history_clean.csv
  customer_flight_activity_clean.csv
  calendar_clean.csv
  airline_loyalty_data_dictionary_clean.csv
  cleaning_audit.csv

The CSV NULL convention is MySQL's \\N token. Use LOAD DATA ... NULL DEFINED BY '\\N'
(or NULLIF(@col,'\\N')) when importing.
"""

from pathlib import Path
import re
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / "01_Original_Data_Airline+Loyalty+Program"
OUTPUT = BASE / "sql_ready"
OUTPUT.mkdir(exist_ok=True)

FILES = {
    "loyalty": SOURCE / "Customer Loyalty History.csv",
    "activity": SOURCE / "Customer Flight Activity.csv",
    "calendar": SOURCE / "Calendar.csv",
    "dictionary": SOURCE / "Airline Loyalty Data Dictionary.csv",
}

def snake_case(name: str) -> str:
    name = str(name).strip()
    name = re.sub(r"[^0-9A-Za-z]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    return name

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [snake_case(c) for c in df.columns]
    return df

def clean_strings(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").str.strip()
        df[c] = df[c].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return df

def month_start(year, month):
    return pd.to_datetime(
        {"year": pd.to_numeric(year, errors="coerce"),
         "month": pd.to_numeric(month, errors="coerce"),
         "day": 1},
        errors="coerce",
    )

def clean_loyalty(path):
    df = clean_strings(normalize_headers(pd.read_csv(path, low_memory=False)))
    audit = []

    df["loyalty_number"] = pd.to_numeric(df["loyalty_number"], errors="coerce").astype("Int64")
    for c in ["salary", "clv", "enrollment_year", "enrollment_month",
              "cancellation_year", "cancellation_month"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Build ISO month-start dates, then replace source year/month pairs.
    df["enrollment_date"] = month_start(df["enrollment_year"], df["enrollment_month"])
    df["cancellation_date"] = month_start(df["cancellation_year"], df["cancellation_month"])

    audit.append(["loyalty", "duplicate_loyalty_number_rows_before", int(df["loyalty_number"].duplicated().sum())])
    audit.append(["loyalty", "missing_loyalty_number_rows", int(df["loyalty_number"].isna().sum())])

    # Negative salary is invalid. Turn it into missing, then impute.
    bad_salary = df["salary"] < 0
    audit.append(["loyalty", "negative_salary_values", int(bad_salary.sum())])
    df.loc[bad_salary, "salary"] = np.nan

    # Negative CLV is invalid; retain as NULL rather than inventing a value.
    bad_clv = df["clv"] < 0
    audit.append(["loyalty", "negative_clv_values", int(bad_clv.sum())])
    df.loc[bad_clv, "clv"] = np.nan

    # Invalid month/year combinations become NULL dates.
    audit.append(["loyalty", "invalid_enrollment_dates", int(df["enrollment_date"].isna().sum())])
    audit.append(["loyalty", "invalid_cancellation_dates", int(
        df["cancellation_date"].isna().sum() - df["cancellation_year"].isna().sum()
    )])

    # Salary imputation: education median, then loyalty-card median, then global median.
    before_salary_missing = int(df["salary"].isna().sum())
    df["salary"] = df["salary"].fillna(df.groupby("education")["salary"].transform("median"))
    df["salary"] = df["salary"].fillna(df.groupby("loyalty_card")["salary"].transform("median"))
    df["salary"] = df["salary"].fillna(df["salary"].median())
    audit.append(["loyalty", "salary_values_imputed", before_salary_missing])

    # Cancellation must not precede enrollment.
    bad_cancel_order = df["cancellation_date"].notna() & (
        df["cancellation_date"] < df["enrollment_date"]
    )
    audit.append(["loyalty", "cancellation_before_enrollment_rows", int(bad_cancel_order.sum())])
    df.loc[bad_cancel_order, "cancellation_date"] = pd.NaT

    # Drop unusable key rows, then deduplicate on the PK.
    df = df.dropna(subset=["loyalty_number", "enrollment_date", "country", "province", "city",
                           "postal_code", "gender", "education", "marital_status",
                           "loyalty_card", "enrollment_type"])
    df = df.drop_duplicates(subset=["loyalty_number"], keep="first")

    df = df[[
        "loyalty_number", "country", "province", "city", "postal_code", "gender",
        "education", "salary", "marital_status", "loyalty_card", "clv",
        "enrollment_type", "enrollment_date", "cancellation_date"
    ]]

    df["loyalty_number"] = df["loyalty_number"].astype("int64")
    df["salary"] = df["salary"].round(2)
    df["clv"] = df["clv"].round(2)
    for c in ["enrollment_date", "cancellation_date"]:
        df[c] = df[c].dt.strftime("%Y-%m-%d").where(df[c].notna(), pd.NA)

    return df, audit

def clean_activity(path, valid_loyalty):
    df = clean_strings(normalize_headers(pd.read_csv(path, low_memory=False)))
    audit = []

    df["loyalty_number"] = pd.to_numeric(df["loyalty_number"], errors="coerce").astype("Int64")
    for c in ["year", "month", "total_flights", "distance", "points_accumulated",
              "points_redeemed", "dollar_cost_points_redeemed"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["activity_date"] = month_start(df["year"], df["month"])
    audit.append(["activity", "invalid_activity_dates", int(df["activity_date"].isna().sum())])

    # Negative activity measures are invalid.
    for c in ["total_flights", "distance", "points_accumulated",
              "points_redeemed", "dollar_cost_points_redeemed"]:
        n = int((df[c] < 0).sum())
        audit.append(["activity", f"negative_{c}_values", n])
        df.loc[df[c] < 0, c] = np.nan

    # Remove invalid keys/dates.
    df = df.dropna(subset=["loyalty_number", "activity_date"])

    # Enforce FK integrity.
    orphan = ~df["loyalty_number"].isin(valid_loyalty)
    audit.append(["activity", "orphan_loyalty_number_rows", int(orphan.sum())])
    df = df.loc[~orphan].copy()

    # The source contains repeated customer-month rows. Aggregate them into
    # one row per loyalty_number + activity_date, preserving monthly totals.
    duplicate_rows = int(df.duplicated(["loyalty_number", "activity_date"]).sum())
    audit.append(["activity", "duplicate_customer_month_rows_aggregated", duplicate_rows])

    metrics = ["total_flights", "distance", "points_accumulated",
               "points_redeemed", "dollar_cost_points_redeemed"]
    df = (df.groupby(["loyalty_number", "activity_date"], as_index=False)[metrics]
            .sum(min_count=1))

    # Metrics are counts/distances/currency and should not be negative after cleaning.
    df["total_flights"] = df["total_flights"].round().astype("int64")
    df["distance"] = df["distance"].round().astype("int64")
    df["points_accumulated"] = df["points_accumulated"].round(2)
    df["points_redeemed"] = df["points_redeemed"].round().astype("int64")
    df["dollar_cost_points_redeemed"] = df["dollar_cost_points_redeemed"].round(2)
    df["activity_date"] = df["activity_date"].dt.strftime("%Y-%m-%d")

    return df, audit

def clean_calendar(path):
    df = clean_strings(normalize_headers(pd.read_csv(path)))
    audit = []

    for c in ["date", "start_of_year", "start_of_quarter", "start_of_month"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
        audit.append(["calendar", f"invalid_{c}", int(df[c].isna().sum())])

    df = df.dropna(subset=["date"]).drop_duplicates(subset=["date"])
    for c in ["date", "start_of_year", "start_of_quarter", "start_of_month"]:
        df[c] = df[c].dt.strftime("%Y-%m-%d").where(df[c].notna(), pd.NA)
    return df, audit

def clean_dictionary(path):
    df = clean_strings(normalize_headers(pd.read_csv(path)))
    df["table"] = df["table"].ffill()
    df = df.drop_duplicates()
    return df[["table", "field", "description"]], []

def write_mysql_csv(df, filename):
    # \\N is MySQL's conventional NULL token for LOAD DATA.
    df.to_csv(OUTPUT / filename, index=False, na_rep="\\N")

def main():
    loyalty, a1 = clean_loyalty(FILES["loyalty"])
    activity, a2 = clean_activity(FILES["activity"], set(loyalty["loyalty_number"]))
    calendar, a3 = clean_calendar(FILES["calendar"])
    dictionary, a4 = clean_dictionary(FILES["dictionary"])

    # Final referential-integrity check.
    assert set(activity["loyalty_number"]).issubset(set(loyalty["loyalty_number"]))

    write_mysql_csv(loyalty, "customer_loyalty_history_clean.csv")
    write_mysql_csv(activity, "customer_flight_activity_clean.csv")
    write_mysql_csv(calendar, "calendar_clean.csv")
    write_mysql_csv(dictionary, "airline_loyalty_data_dictionary_clean.csv")

    audit = pd.DataFrame(a1 + a2 + a3 + a4, columns=["table_name", "check", "count"])
    audit.to_csv(OUTPUT / "cleaning_audit.csv", index=False)

    print("Clean files written to:", OUTPUT.resolve())
    print("Loyalty rows:", len(loyalty))
    print("Activity rows:", len(activity))
    print("Calendar rows:", len(calendar))
    print("Dictionary rows:", len(dictionary))

if __name__ == "__main__":
    main()
