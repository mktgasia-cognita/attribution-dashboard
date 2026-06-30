"""
Build d365_enrichment.csv from an enhanced D365 export.

Only records with a Journey ID (GA cookie) are included -
these are the only ones attributable to marketing channels.

Usage:
    python data/build_d365_enrichment.py <enhanced_csv_path>
"""
import re
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
STITCHED_PATH = SCRIPT_DIR / "bcs_real" / "d365_bq_stitched.csv"
OUTPUT_PATH = SCRIPT_DIR / "bcs_real" / "d365_enrichment.csv"

COLUMN_MAP = {
    "(Do Not Modify) Cognita Opportunity": "d365_id",
    "Applied Grade": "applied_grade",
    "Nationality (Applying Child) (Contact)": "nationality",
    "Admission Status": "admission_status",
    "Applied Academic Year": "academic_year",
    "Current address country (Main Contact 1) (Contact)": "address_country",
    "Offered Grade": "offered_grade",
    "Stage": "d365_stage",
    "Journey ID": "journey_id_raw",
}

KEEP_COLS = [
    "journey_id", "applied_grade", "nationality", "admission_status",
    "academic_year", "address_country",
]

GA_COOKIE_RE = re.compile(r"^GA1\.\d+\.(.+)$")


def extract_cid(raw_journey_id):
    if pd.isna(raw_journey_id):
        return None
    m = GA_COOKIE_RE.match(str(raw_journey_id).strip())
    return m.group(1) if m else None


def format_academic_year(val):
    if pd.isna(val):
        return None
    s = str(int(float(val))) if isinstance(val, (int, float)) else str(val).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:]}"
    return s


def build_enrichment(enhanced_csv_path):
    enhanced = pd.read_csv(enhanced_csv_path, encoding="utf-8-sig")
    enhanced = enhanced.rename(columns=COLUMN_MAP)

    enhanced = enhanced.dropna(subset=["d365_id"])
    total_d365 = len(enhanced)

    with_journey = enhanced.dropna(subset=["journey_id_raw"]).copy()
    without_journey = total_d365 - len(with_journey)
    print(f"D365 records: {total_d365} total, {len(with_journey)} with Journey ID, {without_journey} without")

    with_journey["cid"] = with_journey["journey_id_raw"].apply(extract_cid)
    with_cid = with_journey.dropna(subset=["cid"])
    print(f"Valid CIDs extracted: {len(with_cid)}")

    stitched = pd.read_csv(STITCHED_PATH, dtype={"cid": str})
    merged = with_cid.merge(stitched[["cid", "journey_id"]], on="cid", how="inner")
    print(f"Matched to BCS journey_ids: {len(merged)} of {len(with_cid)} CIDs")

    for col in ["nationality", "address_country", "applied_grade", "admission_status"]:
        if col in merged.columns:
            merged[col] = merged[col].astype(str).str.strip()

    merged["academic_year"] = merged["academic_year"].apply(format_academic_year)

    if merged["journey_id"].duplicated().any():
        dupes = merged["journey_id"].duplicated(keep="first").sum()
        print(f"Deduplicating: {dupes} duplicate journey_ids removed (keeping first)")
        merged = merged.drop_duplicates(subset=["journey_id"], keep="first")

    output = merged[KEEP_COLS].sort_values("journey_id")
    output.to_csv(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(output)} enrichment records to {OUTPUT_PATH}")
    print(f"Coverage: {len(output)} of {total_d365} D365 records attributable ({len(output)/total_d365*100:.0f}%)")

    print(f"\nGrade distribution:")
    print(output["applied_grade"].value_counts().to_string())
    print(f"\nNationality distribution:")
    print(output["nationality"].value_counts().to_string())
    print(f"\nAdmission status distribution:")
    print(output["admission_status"].value_counts().to_string())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <enhanced_csv_path>")
        sys.exit(1)
    build_enrichment(sys.argv[1])
