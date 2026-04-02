#!/usr/bin/env python3
"""
3_message_drafter.py — Personalized Message Drafting via Claude API
=====================================================================
Reads contacts.csv (Script 2) and companies_researched.csv (Script 1),
selects the right template for each contact, asks Claude to produce a
personalized outreach message, and writes all drafts to data/messages_drafted.csv.

Run:
    python 3_message_drafter.py
"""

import csv
import os
import time

import anthropic

import config

# ---------------------------------------------------------------------------
# Template loader
# ---------------------------------------------------------------------------

def load_templates() -> dict[str, str]:
    """
    Load all .txt files from the templates/ directory.
    Returns a dict keyed by filename stem, e.g. {"procurement": "...", "engineering": "..."}.
    """
    templates = {}
    if not os.path.isdir(config.TEMPLATES_DIR):
        raise FileNotFoundError(
            f"Templates directory not found: {config.TEMPLATES_DIR}\n"
            "Create it and add at least one .txt template file."
        )
    for fname in os.listdir(config.TEMPLATES_DIR):
        if fname.endswith(".txt"):
            key = os.path.splitext(fname)[0].lower()
            with open(os.path.join(config.TEMPLATES_DIR, fname), encoding="utf-8") as f:
                templates[key] = f.read().strip()

    if not templates:
        raise FileNotFoundError(
            f"No .txt template files found in {config.TEMPLATES_DIR}. "
            "Add at least one template."
        )
    return templates


def select_template(contact_title: str, templates: dict[str, str]) -> tuple[str, str]:
    """
    Pick the best template for a given contact title.
    Falls back to the 'default' template if no keyword matches.
    Returns (template_key, template_text).
    """
    title_lower = contact_title.lower()

    # Keyword → template key mapping (order matters — first match wins)
    keyword_map = [
        (["procurement", "supply chain", "sourcing", "purchasing"], "procurement"),
        (["engineer", "cto", "chief engineer", "technical"], "engineering"),
        (["business development", "partnerships", "bd"], "business_development"),
        (["operations", "coo", "vp operations"], "operations"),
        (["ceo", "president", "founder", "owner"], "executive"),
    ]

    for keywords, template_key in keyword_map:
        if any(kw in title_lower for kw in keywords) and template_key in templates:
            return template_key, templates[template_key]

    # Fall back to 'default' or the first available template
    fallback_key = "default" if "default" in templates else next(iter(templates))
    return fallback_key, templates[fallback_key]


# ---------------------------------------------------------------------------
# Company research lookup
# ---------------------------------------------------------------------------

def load_company_research() -> dict[str, dict]:
    """
    Load companies_researched.csv into a dict keyed by lowercase company name.
    """
    research = {}
    if not os.path.exists(config.COMPANIES_RESEARCHED_CSV):
        print(
            f"Warning: {config.COMPANIES_RESEARCHED_CSV} not found. "
            "Messages will be drafted without company research context."
        )
        return research

    with open(config.COMPANIES_RESEARCHED_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = row.get("company_name", "").strip().lower()
            if key:
                research[key] = row
    return research


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------

def draft_message(
    client: anthropic.Anthropic,
    contact: dict,
    company_info: dict,
    template_text: str,
) -> dict[str, str]:
    """
    Ask Claude to write a personalized outreach message.
    Returns a dict with subject_line and message_body.
    """
    company_context = ""
    if company_info:
        company_context = f"""
Company Intelligence:
- Description: {company_info.get('description', 'N/A')}
- Focus Areas: {company_info.get('focus_areas', 'N/A')}
- Funding Stage: {company_info.get('funding_stage', 'N/A')}
- Recent News: {company_info.get('recent_news', 'N/A')}
- ICP Fit Notes: {company_info.get('icp_fit_notes', 'N/A')}
""".strip()

    prompt = f"""
You are an expert B2B sales copywriter specializing in aerospace and defense.

Your task: Write a highly personalized cold outreach email using the template and
contact/company details below. The email must feel human and genuine — not a template blast.

Contact Details:
- Name: {contact['contact_name']}
- Title: {contact['title']}
- Company: {contact['company_name']}

{company_context}

Message Template (follow the structure and tone, but personalize every section):
---
{template_text}
---

Instructions:
1. Open with a specific reference to something real about the company or contact's role.
2. Keep the total message under 150 words.
3. One clear call-to-action — a brief call or quick reply.
4. Do NOT use hollow phrases like "I hope this finds you well" or "I wanted to reach out".
5. Write a compelling subject line (under 10 words).

Respond in this exact JSON format (no markdown, no code fences):
{{
  "subject_line": "<subject line here>",
  "message_body": "<full email body here>"
}}
""".strip()

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.CLAUDE_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rstrip("```").strip()

    import json
    parsed = json.loads(raw)
    return {
        "subject_line": parsed.get("subject_line", "").strip(),
        "message_body": parsed.get("message_body", "").strip(),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    # Validate API key
    if config.ANTHROPIC_API_KEY == "YOUR_ANTHROPIC_API_KEY":
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set in config.py. "
            "Add your key before running this script."
        )

    # Load inputs
    if not os.path.exists(config.CONTACTS_CSV):
        raise FileNotFoundError(
            f"Input file not found: {config.CONTACTS_CSV}\n"
            "Run 2_contact_finder.py first."
        )

    templates       = load_templates()
    company_lookup  = load_company_research()

    with open(config.CONTACTS_CSV, newline="", encoding="utf-8") as f:
        contacts = list(csv.DictReader(f))

    if not contacts:
        print("No contacts found in contacts.csv. Exiting.")
        return

    print(f"Found {len(contacts)} contacts. Drafting messages with Claude …\n")
    print(f"Available templates: {list(templates.keys())}\n")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    fieldnames = [
        "contact_name", "company_name", "title", "email",
        "subject_line", "message_body", "template_used",
    ]
    os.makedirs(os.path.dirname(config.MESSAGES_DRAFTED_CSV), exist_ok=True)

    with open(config.MESSAGES_DRAFTED_CSV, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, contact in enumerate(contacts, start=1):
            name    = contact.get("contact_name", "Unknown")
            company = contact.get("company_name", "")
            title   = contact.get("title", "")

            print(f"[{idx}/{len(contacts)}] {name} @ {company} ({title}) …")

            # Look up company research
            company_info = company_lookup.get(company.lower(), {})

            # Select template
            template_key, template_text = select_template(title, templates)
            print(f"    Template: {template_key}")

            try:
                drafted = draft_message(client, contact, company_info, template_text)

                writer.writerow({
                    "contact_name":  name,
                    "company_name":  company,
                    "title":         title,
                    "email":         contact.get("email", "N/A"),
                    "subject_line":  drafted["subject_line"],
                    "message_body":  drafted["message_body"],
                    "template_used": template_key,
                })
                print(f"    Subject: {drafted['subject_line']}")

            except Exception as exc:
                print(f"    [Error] {exc}")
                writer.writerow({
                    "contact_name":  name,
                    "company_name":  company,
                    "title":         title,
                    "email":         contact.get("email", "N/A"),
                    "subject_line":  "DRAFT FAILED — retry manually",
                    "message_body":  str(exc),
                    "template_used": template_key,
                })

            # Brief pause between Claude calls
            if idx < len(contacts):
                time.sleep(0.5)

    print(f"\nDone. Messages saved to: {config.MESSAGES_DRAFTED_CSV}")


if __name__ == "__main__":
    main()
