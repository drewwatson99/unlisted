#!/usr/bin/env python3
"""
Build the Unlisted broker dataset from primary public-record sources.

Sources (all public records or independently verified facts):
  1. California Data Broker Registry (CPPA) - current registration year
  2. California Data Broker Registry (CPPA) - complete historical registrations
  3. curated.json - hand-verified people-search opt-out URLs maintained in this repo

Every record carries a `sources` array so provenance is auditable.

Usage:
    python3 scripts/build_dataset.py [--refresh]

    --refresh   re-download the CPPA registry CSVs before building
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import date
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

CPPA_CURRENT = "https://cppa.ca.gov/data_broker_registry/registry.csv"
CPPA_COMPLETE = "https://cppa.ca.gov/data_broker_registry/complete-reg-data-brokers.csv"

CURRENT_CSV = os.path.join(HERE, "ca_registry_2026.csv")
COMPLETE_CSV = os.path.join(HERE, "ca_registry_complete.csv")
CURATED_JSON = os.path.join(HERE, "curated.json")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def norm_domain(url):
    """Reduce a URL to a bare comparable domain."""
    if not url:
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def clean_email(raw):
    """CPPA obfuscates some addresses as 'privacy [at] example.com'."""
    if not raw:
        return ""
    e = raw.strip().lower()
    e = e.replace(" [at] ", "@").replace("[at]", "@")
    e = e.replace(" [dot] ", ".").replace("[dot]", ".")
    e = e.split(",")[0].split(";")[0].split()[0] if e else ""
    return e if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e) else ""


def first_url(text):
    """Pull the first http(s) URL out of a blob of free text."""
    if not text:
        return ""
    m = re.search(r"https?://[^\s,\)\]\"'<>]+", text)
    return m.group(0).rstrip(".,);") if m else ""


def yes(v):
    return str(v).strip().lower() in ("yes", "true", "y", "1")


def to_int(v):
    try:
        return int(str(v).strip().replace(",", ""))
    except (ValueError, AttributeError):
        return None


def to_float(v):
    try:
        return float(str(v).strip().replace(",", ""))
    except (ValueError, AttributeError):
        return None


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f)]


def download(url, dest):
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "unlisted-dataset-builder"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as out:
        out.write(r.read())


# --------------------------------------------------------------------------
# source parsers
# --------------------------------------------------------------------------

def parse_current(rows):
    """Current-year CPPA registry. Richest source: contact, rights URL,
    sensitive-data flags, onward-sale disclosures, and compliance stats."""
    out = []
    for r in rows:
        name = r.get("Data broker name:", "").strip()
        if not name:
            continue

        website = r.get("Data broker primary website:", "").strip()
        rights_url = r.get(
            "Data broker's primary website that contains details on how "
            "consumers can exercise their CA Consumer Privacy rights:", "").strip()

        recv = to_int(r.get("Requests to delete - Total requests received"))
        whole = to_int(r.get("Requests to delete - Total requests received - Complied in whole"))
        part = to_int(r.get("Requests to delete - Total requests received - Complied in part"))
        denied = to_int(r.get("Requests to delete - Total requests received - Denied"))
        median_days = to_float(
            r.get("Requests to delete - The number of days to respond substantively "
                  "to a request to delete in 2024 - Median"))

        compliance = None
        if recv and recv > 0 and whole is not None:
            compliance = round((whole + (part or 0)) / recv, 3)

        out.append({
            "name": name,
            "dba": r.get("Doing Business As (DBA), if applicable:", "").strip(),
            "website": website,
            "domain": norm_domain(website),
            "email": clean_email(r.get("Data broker primary contact email address:")),
            "phone": r.get("Data broker primary phone number: [optional]", "").strip(),
            "opt_out_url": first_url(rights_url) or rights_url,
            "ca_registered": True,
            "collects_minors": yes(r.get("Data broker collects personal information of minors:")),
            "collects_biometric": yes(r.get("Data broker collects consumers' biometric data")),
            "collects_geolocation": yes(r.get("Data broker collects consumers' precise geolocation")),
            "collects_reproductive_health": yes(r.get("Data broker collects consumers’ reproductive health care data:")),
            "collects_citizenship": yes(r.get("Data broker collects consumers' citizenship data, including immigration status")),
            "collects_sexual_orientation": yes(r.get("Data broker collects consumers' sexual orientation status")),
            "collects_gov_id": yes(r.get("Data broker collects consumers’ government‑issued identification numbers used to verify an individual’s identity")),
            "sold_to_foreign_actor": yes(r.get("Data broker shared or sold consumers' data to a foreign actor in the past year")),
            "sold_to_federal_gov": yes(r.get("Data broker shared or sold consumers' data to the federal government in the past year")),
            "sold_to_law_enforcement": yes(r.get("Data broker shared or sold consumers’ data to law enforcement in the past year, except when required by subpoena or court order")),
            "sold_to_genai": yes(r.get("Data broker shared or sold consumers’ data to a developer of a GenAI system or model in the past year")),
            "deletion_requests_received": recv,
            "deletion_compliance_rate": compliance,
            "deletion_median_response_days": median_days,
            "sources": ["cppa-registry-current"],
        })
    return out


def parse_complete(rows):
    """Historical CPPA registrations (2020+). Thinner, but catches brokers
    that registered previously and may still be operating."""
    out = []
    for r in rows:
        name = r.get("Data Broker Name", "").strip()
        if not name:
            continue
        website = r.get("Website URL", "").strip()
        optout_blob = r.get(
            "How a consumer may opt out of sale or submit requests under the CCPA", "")
        out.append({
            "name": name,
            "website": website,
            "domain": norm_domain(website),
            "email": clean_email(r.get("Email Address")),
            "opt_out_url": first_url(optout_blob),
            "ca_registered": True,
            "date_added": r.get("Date Added", "").strip(),
            "sources": ["cppa-registry-historical"],
        })
    return out


def parse_curated(path):
    """Hand-verified people-search entries maintained in this repo.

    These are independently confirmed facts (a company's own published
    opt-out URL), not a copy of any third party's compilation."""
    if not os.path.exists(path):
        print("  curated.json not found - skipping")
        return []
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:
        r.setdefault("sources", [])
        if "curated" not in r["sources"]:
            r["sources"].append("curated")
        r["domain"] = r.get("domain") or norm_domain(r.get("website", ""))
    return rows


# --------------------------------------------------------------------------
# merge + derive
# --------------------------------------------------------------------------

MERGE_PREFER = ("opt_out_url", "email", "phone", "website", "category",
                "search_url", "removal_method", "notes", "verification")


def merge(*groups):
    """Merge on normalized domain, falling back to lowercased name."""
    merged = {}
    for group in groups:
        for rec in group:
            key = rec.get("domain") or rec["name"].lower()
            if key not in merged:
                merged[key] = dict(rec)
                continue
            tgt = merged[key]
            # richer non-empty values win; sources accumulate
            for field in MERGE_PREFER:
                if not tgt.get(field) and rec.get(field):
                    tgt[field] = rec[field]
            for k, v in rec.items():
                if k in ("sources", "name") or k in MERGE_PREFER:
                    continue
                if tgt.get(k) in (None, "", False) and v not in (None, "", False):
                    tgt[k] = v
            for s in rec.get("sources", []):
                if s not in tgt["sources"]:
                    tgt["sources"].append(s)
    return list(merged.values())


def build_leverage(records):
    """Map shared opt-out backends: one submission can clear many brokers.

    This is the highest-value derived signal in the dataset - it tells a
    user which single actions have outsized reach."""
    hubs = defaultdict(list)
    for r in records:
        url = r.get("opt_out_url")
        if not url:
            continue
        host = norm_domain(url)
        own = r.get("domain")
        # only a hub if the opt-out lives on a *different* domain
        if host and own and host != own:
            hubs[host].append(r["name"])

    leverage = {h: sorted(names) for h, names in hubs.items() if len(names) >= 2}

    by_host = {}
    for host, names in leverage.items():
        by_host[host] = len(names)
    for r in records:
        host = norm_domain(r.get("opt_out_url", ""))
        r["leverage"] = by_host.get(host, 1) if r.get("opt_out_url") else 0
        r["opt_out_hub"] = host if host and by_host.get(host) else ""
    return leverage


def sensitivity(r):
    """0-7 count of especially sensitive categories this broker self-reports."""
    return sum(bool(r.get(k)) for k in (
        "collects_minors", "collects_biometric", "collects_geolocation",
        "collects_reproductive_health", "collects_citizenship",
        "collects_sexual_orientation", "collects_gov_id"))


def onward_sale(r):
    """0-4 count of concerning onward-sale disclosures."""
    return sum(bool(r.get(k)) for k in (
        "sold_to_foreign_actor", "sold_to_federal_gov",
        "sold_to_law_enforcement", "sold_to_genai"))


# How much real-world harm the category represents to an individual.
# People-search sites publish your home address to anyone with a browser,
# so they dominate; marketing brokers are invisible but feed everyone else.
CATEGORY_WEIGHT = {
    "people-search": 45,
    "face-search": 38,
    "phone-directory": 26,
    "public-record": 20,
    "b2b": 18,
    "marketing": 10,
}


def score(records):
    """Composite priority score. Higher = do this one sooner.

    Five weighted signals, all derived from public record or verified fact:

      category   how exposed the data is to a casual searcher
      reach      log-scaled deletion-request volume the broker self-reported
                 to California - a genuine proxy for how many people this
                 broker actually affects
      leverage   how many other brokers one submission also clears
      sensitivity / onward sale   what they collect and who they sell it to
      non-compliance              how often they deny deletion requests

    Non-compliance raises priority rather than lowering it: a broker that
    denies half its requests is one you need to start early and chase.
    """
    for r in records:
        s = float(CATEGORY_WEIGHT.get(r.get("category"), 12))

        # reach: log-scaled so 26M requests doesn't swamp everything else
        recv = r.get("deletion_requests_received") or 0
        if recv > 0:
            s += min(math.log10(recv) * 4.5, 30)

        s += min(r.get("leverage", 0), 60) * 1.2
        s += sensitivity(r) * 3.5
        s += onward_sale(r) * 4.5

        rate = r.get("deletion_compliance_rate")
        if rate is not None:
            # only meaningful at volume; a 0% rate on 3 requests is noise
            weight = min((recv or 0) / 1000.0, 1.0)
            s += (1 - rate) * 20 * weight

        if r.get("opt_out_url"):
            s += 6                       # actionable right now
        if r.get("email"):
            s += 4                       # letter route available
        if r.get("search_url"):
            s += 8                       # confirmed publicly name-searchable

        r["sensitivity_score"] = sensitivity(r)
        r["onward_sale_score"] = onward_sale(r)
        r["priority_score"] = round(s, 1)

    ranked = sorted(records, key=lambda x: (-x["priority_score"], x["name"].lower()))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return ranked


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

CSV_FIELDS = [
    "rank", "name", "domain", "category", "opt_out_url", "email", "phone",
    "opt_out_hub", "leverage", "priority_score", "sensitivity_score",
    "onward_sale_score", "ca_registered", "collects_minors",
    "sold_to_genai", "sold_to_law_enforcement",
    "deletion_requests_received", "deletion_compliance_rate",
    "deletion_median_response_days", "removal_method", "sources",
]


def write_outputs(records, leverage):
    os.makedirs(DATA, exist_ok=True)

    with open(os.path.join(DATA, "brokers.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    with open(os.path.join(DATA, "leverage.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"generated": date.today().isoformat(),
             "hubs": {h: {"clears": len(n), "brokers": n}
                      for h, n in sorted(leverage.items(), key=lambda x: -len(x[1]))}},
            f, indent=2, ensure_ascii=False)

    with open(os.path.join(DATA, "brokers.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in records:
            row = dict(r)
            row["sources"] = "|".join(r.get("sources", []))
            w.writerow(row)

    actionable = [r for r in records if r.get("opt_out_url") or r.get("email")]
    stats = {
        "generated": date.today().isoformat(),
        "total_brokers": len(records),
        "actionable": len(actionable),
        "with_opt_out_url": sum(1 for r in records if r.get("opt_out_url")),
        "with_email": sum(1 for r in records if r.get("email")),
        "people_search": sum(1 for r in records if r.get("category") == "people-search"),
        "ca_registered": sum(1 for r in records if r.get("ca_registered")),
        "collects_minors": sum(1 for r in records if r.get("collects_minors")),
        "sold_to_genai": sum(1 for r in records if r.get("sold_to_genai")),
        "hubs": len(leverage),
    }
    with open(os.path.join(DATA, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # The web app is static and fetches its data relatively, so keep a copy
    # alongside it. Trimmed to the fields the UI actually uses.
    web_fields = (
        "rank", "name", "domain", "website", "category", "opt_out_url",
        "search_url", "email", "phone", "opt_out_hub", "leverage",
        "priority_score", "sensitivity_score", "onward_sale_score",
        "collects_minors", "sold_to_genai", "sold_to_law_enforcement",
        "deletion_requests_received", "deletion_compliance_rate",
        "deletion_median_response_days", "verification", "removal_method",
        "notes", "ca_registered",
    )
    slim = [{k: r[k] for k in web_fields if r.get(k) not in (None, "", False)}
            for r in records]
    web_dir = os.path.join(ROOT, "web")
    os.makedirs(web_dir, exist_ok=True)
    with open(os.path.join(web_dir, "brokers.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": stats["generated"], "brokers": slim},
                  f, separators=(",", ":"), ensure_ascii=False)

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-download CPPA registry CSVs first")
    args = ap.parse_args()

    if args.refresh or not os.path.exists(CURRENT_CSV):
        print("Refreshing source data from CPPA...")
        download(CPPA_CURRENT, CURRENT_CSV)
        download(CPPA_COMPLETE, COMPLETE_CSV)

    print("Parsing sources...")
    current = parse_current(read_csv(CURRENT_CSV))
    print(f"  CPPA current registry:    {len(current):>4}")
    complete = parse_complete(read_csv(COMPLETE_CSV))
    print(f"  CPPA historical registry: {len(complete):>4}")
    curated = parse_curated(CURATED_JSON)
    print(f"  curated people-search:    {len(curated):>4}")

    # curated first so its hand-verified opt-out URLs win on conflict
    records = merge(curated, current, complete)
    print(f"\nMerged unique brokers: {len(records)}")

    leverage = build_leverage(records)
    records = score(records)
    stats = write_outputs(records, leverage)

    print("\nWrote data/brokers.json, brokers.csv, leverage.json, stats.json")
    print("\nDataset summary")
    for k, v in stats.items():
        print(f"  {k:<22} {v}")
    print("\nTop 10 by priority:")
    for r in records[:10]:
        print(f"  {r['rank']:>3}. {r['name'][:44]:<44} "
              f"score={r['priority_score']:<6} leverage={r.get('leverage', 0)}")


if __name__ == "__main__":
    sys.exit(main())
