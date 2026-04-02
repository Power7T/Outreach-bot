#!/usr/bin/env python3
"""
1_company_research.py — Company Research via Perplexity API
=============================================================
Reads a list of target aerospace companies from data/target_companies.csv,
queries the Perplexity API for structured company intelligence, and writes
enriched results to data/companies_researched.csv.

Run:
    python 1_company_research.py
"""

import csv
import json
import os
import time
import requests

import config

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_research_prompt(company_name: str) -> str:
    """Return a structured Perplexity prompt for a single company."""
    return f"""
Research the aerospace/defense company "{company_name}" and provide the following
information in valid JSON — no markdown, no code fences, just raw JSON:

{{
  "company_name": "<official company name>",
  "website": "<primary website URL>",
  "description": "<2–3 sentence company overview>",
  "employee_count": "<approximate headcount or range>",
  "headquarters": "<city, country>",
  "focus_areas": "<comma-separated list of product/service focus areas>",
  "funding_stage": "<bootstrapped / Series A / Series B / public / subsidiary / unknown>",
  "recent_news": "<one sentence summary of the most recent notable event, funding, contract, or product announcement>",
  "icp_fit_notes": "<assessment of fit against the following ICP criteria:\n{config.ICP_CRITERIA}\nBe concise.>"
}}

If any field is unknown, use "N/A".
""".strip()


# ---------------------------------------------------------------------------
# Perplexity API call
# ---------------------------------------------------------------------------

def query_perplexity(prompt: str, retries: int = 3, backoff: float = 2.0) -> dict | None:
    """
    Call the Perplexity chat-completions endpoint and return parsed JSON.
    Returns None on unrecoverable failure.
    """
    headers = {
        "Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a B2B market-research assistant. "
                    "Return ONLY valid JSON — no prose, no markdown, no code fences."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            raw_text = response.json()["choices"][0]["message"]["content"].strip()

            # Strip accidental markdown fences if the model adds them
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            return json.loads(raw_text)

        except requests.exceptions.HTTPError as exc:
            print(f"    [HTTP {exc.response.status_code}] attempt {attempt}/{retries}: {exc}")
        except json.JSONDecodeError as exc:
            print(f"    [JSON parse error] attempt {attempt}/{retries}: {exc}")
        except Exception as exc:
            print(f"    [Error] attempt {attempt}/{retries}: {exc}")

        if attempt < retries:
            sleep_time = backoff * attempt
            print(f"    Retrying in {sleep_time:.0f}s …")
            time.sleep(sleep_time)

    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    # Validate API key is set
    if config.PERPLEXITY_API_KEY == "YOUR_PERPLEXITY_API_KEY":
        raise EnvironmentError(
            "PERPLEXITY_API_KEY is not set in config.py. "
            "Add your key before running this script."
        )

    # Read input companies
    if not os.path.exists(config.INPUT_COMPANIES_CSV):
        raise FileNotFoundError(
            f"Input file not found: {config.INPUT_COMPANIES_CSV}\n"
            "Create it with at least a 'company_name' column."
        )

    with open(config.INPUT_COMPANIES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        companies = [row["company_name"].strip() for row in reader if row.get("company_name")]

    if not companies:
        print("No companies found in input CSV. Exiting.")
        return

    print(f"Found {len(companies)} companies to research.\n")

    # Output CSV columns
    fieldnames = [
        "company_name",
        "website",
        "description",
        "employee_count",
        "headquarters",
        "focus_areas",
        "funding_stage",
        "recent_news",
        "icp_fit_notes",
    ]

    os.makedirs(os.path.dirname(config.COMPANIES_RESEARCHED_CSV), exist_ok=True)

    with open(config.COMPANIES_RESEARCHED_CSV, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for idx, company in enumerate(companies, start=1):
            print(f"[{idx}/{len(companies)}] Researching: {company} …")
            prompt = build_research_prompt(company)
            result = query_perplexity(prompt)

            if result:
                writer.writerow(result)
                print(f"    OK — {result.get('description', '')[:80]}…")
            else:
                # Write a placeholder row so the pipeline can continue
                writer.writerow({
                    "company_name": company,
                    "website": "N/A",
                    "description": "Research failed — retry manually",
                    "employee_count": "N/A",
                    "headquarters": "N/A",
                    "focus_areas": "N/A",
                    "funding_stage": "N/A",
                    "recent_news": "N/A",
                    "icp_fit_notes": "N/A",
                })
                print(f"    FAILED — placeholder row written.")

            # Polite delay to avoid rate-limiting
            if idx < len(companies):
                time.sleep(1.5)

    print(f"\nDone. Results saved to: {config.COMPANIES_RESEARCHED_CSV}")


if __name__ == "__main__":
    main()
