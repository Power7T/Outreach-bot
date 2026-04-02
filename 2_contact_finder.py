#!/usr/bin/env python3
"""
2_contact_finder.py — Contact Finder via Apollo.io
====================================================
Reads companies_researched.csv (output of Script 1), queries the Apollo.io
People Search API for decision-maker contacts at each company, and writes
results to data/contacts.csv.

Run:
    python 2_contact_finder.py
"""

import csv
import os
import time
import requests

import config

# ---------------------------------------------------------------------------
# Apollo.io API helpers
# ---------------------------------------------------------------------------

APOLLO_PEOPLE_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"


def search_contacts(company_name: str, company_website: str) -> list[dict]:
    """
    Query Apollo People Search for decision-maker contacts at a given company.
    Returns a list of cleaned contact dicts (up to APOLLO_CONTACTS_PER_COMPANY).
    """
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": config.APOLLO_API_KEY,
    }

    # Build the search payload
    payload = {
        "page": 1,
        "per_page": config.APOLLO_CONTACTS_PER_COMPANY,
        "organization_domains": [_strip_domain(company_website)] if company_website and company_website != "N/A" else [],
        "q_organization_name": company_name,
        "person_seniorities": config.APOLLO_SENIORITY_FILTERS,
        "person_titles": config.APOLLO_TITLE_KEYWORDS,
        "contact_email_status": ["verified", "likely to engage"],
    }

    try:
        response = requests.post(
            APOLLO_PEOPLE_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        people = data.get("people") or data.get("contacts") or []
        return [_parse_person(p, company_name) for p in people]

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code
        if status == 422:
            print(f"    [Apollo 422] Unprocessable entity for '{company_name}' — skipping.")
        elif status == 401:
            raise EnvironmentError("Apollo API key is invalid or expired. Check config.py.")
        else:
            print(f"    [Apollo HTTP {status}] {exc}")
    except Exception as exc:
        print(f"    [Apollo Error] {exc}")

    return []


def _strip_domain(url: str) -> str:
    """Extract bare domain from a URL (e.g. https://www.example.com → example.com)."""
    url = url.lower().replace("https://", "").replace("http://", "").replace("www.", "")
    return url.split("/")[0].strip()


def _parse_person(person: dict, fallback_company: str) -> dict:
    """Flatten an Apollo person object into the columns we need."""
    org = person.get("organization") or {}
    return {
        "company_name": org.get("name") or fallback_company,
        "contact_name": (
            f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
        ),
        "title": person.get("title", "N/A"),
        "email": person.get("email", "N/A"),
        "linkedin_url": person.get("linkedin_url", "N/A"),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    # Validate API key
    if config.APOLLO_API_KEY == "YOUR_APOLLO_API_KEY":
        raise EnvironmentError(
            "APOLLO_API_KEY is not set in config.py. "
            "Add your key before running this script."
        )

    # Read researched companies
    if not os.path.exists(config.COMPANIES_RESEARCHED_CSV):
        raise FileNotFoundError(
            f"Input file not found: {config.COMPANIES_RESEARCHED_CSV}\n"
            "Run 1_company_research.py first."
        )

    with open(config.COMPANIES_RESEARCHED_CSV, newline="", encoding="utf-8") as f:
        companies = list(csv.DictReader(f))

    if not companies:
        print("No companies found in researched CSV. Exiting.")
        return

    print(f"Found {len(companies)} companies. Searching for contacts …\n")

    fieldnames = ["company_name", "contact_name", "title", "email", "linkedin_url"]
    os.makedirs(os.path.dirname(config.CONTACTS_CSV), exist_ok=True)

    total_contacts = 0

    with open(config.CONTACTS_CSV, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, company in enumerate(companies, start=1):
            name    = company.get("company_name", "").strip()
            website = company.get("website", "").strip()

            print(f"[{idx}/{len(companies)}] {name} …")

            contacts = search_contacts(name, website)

            if contacts:
                writer.writerows(contacts)
                total_contacts += len(contacts)
                print(f"    Found {len(contacts)} contact(s).")
                for c in contacts:
                    print(f"      • {c['contact_name']} — {c['title']} ({c['email']})")
            else:
                print(f"    No contacts found — skipping.")

            # Respect Apollo rate limits (300 req/min on paid plans)
            if idx < len(companies):
                time.sleep(0.5)

    print(f"\nDone. {total_contacts} contacts saved to: {config.CONTACTS_CSV}")


if __name__ == "__main__":
    main()
