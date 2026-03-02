#!/usr/bin/env python3
"""
ModelIt Daily Outreach — Email + HubSpot Sync
Reads district contacts.md, sends personalized outreach emails to ALL contacts
via gogcli, creates HubSpot contacts/deals, and logs email in HubSpot.

Strategy: Send to ALL contacts at once per district (no wave delays).
Sender: charles@discoverycollective.com
Signature: Dr. Marie Martin & Dr. Charles Martin

Updated 2026-03-02 — Per-contact personalized pitch hooks
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_DIR / "data" / "cde-districts.json"
OUTREACH_LOG = REPO_DIR / "data" / "outreach-log.jsonl"

# HubSpot API
HUBSPOT_TOKEN = os.environ.get("HUBSPOT_TOKEN", "")
if not HUBSPOT_TOKEN:
    print("WARNING: HUBSPOT_TOKEN not set - HubSpot sync disabled")
HUBSPOT_API = "https://api.hubapi.com"

# Telegram group for notifications (ModelIt LCAP Agent)
TELEGRAM_GROUP = os.environ.get("TELEGRAM_GROUP", "-5188258108")

# Email sender
FROM_EMAIL = "charles@discoverycollective.com"
GOG_CLIENT = "dc"

# Email assets (hosted on GitHub - must use master branch)
IMG_BASE = "https://raw.githubusercontent.com/charlesmartinedd/modelit-district-intel/master/_reference/email-assets"
SCREENSHOT_BUILD = f"{IMG_BASE}/modelit-build-it.png"
SCREENSHOT_RUN = f"{IMG_BASE}/modelit-run-it.png"
MICROMAYHEM_VIDEO = "https://drive.google.com/file/d/1Xn6Ucu-tvC2wlttQhoCWHiyCqFxhiWnT/view?usp=drive_link"



def clean_district_name(name):
    """Strip internal suffixes like Intelligence Profile that should never appear in emails."""
    name = re.sub(r"\s*[-\u2014\u2013]+\s*(?:Full\s+)?(?:District\s+)?Intelligence\s+Profile\s*$", "", name, flags=re.IGNORECASE)
    return name.strip()

def run_cmd(cmd, check=True):
    """Run a shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"CMD FAILED: {cmd}\n{result.stderr}")
    return result


def hubspot_request(method, endpoint, data=None):
    """Make a HubSpot API request."""
    if not HUBSPOT_TOKEN:
        return None
    url = f"{HUBSPOT_API}{endpoint}"
    import urllib.request
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {HUBSPOT_TOKEN}")
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  HubSpot API error: {e}")
        return None


def parse_all_contacts(district_slug):
    """Parse contacts.md to extract ALL contacts with name, title, email, pitch hook, and notes."""
    path = REPO_DIR / "districts" / district_slug / "contacts.md"
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8", errors="replace")
    contacts = []

    # Split into sections by ### headers (each contact)
    sections = re.split(r"^### ", content, flags=re.MULTILINE)

    for section in sections[1:]:  # skip pre-header content
        lines = section.strip().split("\n")
        if not lines:
            continue

        # First line is "Name - Title" or just "Name"
        header = lines[0].strip()
        name_match = re.match(r"^(.+?)(?:\s*[-\u2014\u2013]\s*(.+))?$", header)
        if not name_match:
            continue

        name = name_match.group(1).strip()
        title = name_match.group(2).strip() if name_match.group(2) else ""

        # Parse table rows for email, title, phone, pitch hook, notes, why tier
        email = None
        phone = ""
        pitch_hook = ""
        notes = ""
        why_tier = ""
        for line in lines[1:]:
            line_stripped = line.strip()
            # Match table rows: "| Key | Value |" (standard tables)
            row_match = re.match(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line_stripped)
            if row_match:
                key = row_match.group(1).strip().lower()
                val = row_match.group(2).strip()
                if key == "email":
                    email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", val)
                    if email_match:
                        email = email_match.group(0)
                elif key == "title" and not title:
                    title = val
                elif key == "phone":
                    phone = val
                elif key == "pitch hook":
                    pitch_hook = val.strip('"').strip("'")
                elif key == "notes":
                    notes = val
                elif key in ("why tier 1", "why tier 2", "why tier 3", "why tier 3b",
                             "why tier 4", "why tier 4b", "why tier 4c", "why tier 4d",
                             "why tier 5", "why tier"):
                    why_tier = val

        if email:
            contacts.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
                "pitch_hook": pitch_hook,
                "notes": notes,
                "why_tier": why_tier,
            })

    return contacts


def parse_district_hook(district_slug):
    """Parse entry-strategy.md for the district hook."""
    path = REPO_DIR / "districts" / district_slug / "entry-strategy.md"
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8", errors="replace")
    hook_match = re.search(r'## The Hook\s*\n\n> "(.+?)"', content, re.DOTALL)
    if hook_match:
        hook = hook_match.group(1).strip().replace("\n> ", " ")
        # Ensure we/us pronouns (never I/me)
        hook = hook.replace(" I ", " we ").replace(" my ", " our ").replace(" me ", " us ")
        return hook
    return None


def shorten_district(name):
    """Remove common suffixes for cleaner display."""
    for suffix in [
        " Unified School District", " Union School District",
        " Elementary School District", " School District", " Unified",
    ]:
        name = name.replace(suffix, "")
    return name


def build_email_html(district_name, contact, district_hook=None):
    """Build personalized HTML email using per-contact pitch hooks.

    Personalization priority:
    1. Contact's own pitch_hook from contacts.md (most specific)
    2. District-wide hook from entry-strategy.md (fallback)
    3. Generic hook (last resort)

    Rules:
    - All pronouns: we/us (never I/me)
    - NGSS mentioned only once
    - Platform screenshots first, then MicroMayhem game
    - Signature: Dr. Marie Martin & Dr. Charles Martin
    - Reply goes to charles@discoverycollective.com
    - "Email" hyperlink in signature
    """
    first_name = contact["name"].split()[0] if contact.get("name") else "there"
    short_name = shorten_district(district_name)

    # Per-contact personalization: use their specific pitch hook if available
    contact_hook = contact.get("pitch_hook", "")

    # Skip logistics-only contacts (e.g., "N/A - scheduling contact")
    if contact_hook and "n/a" in contact_hook.lower():
        contact_hook = ""

    if contact_hook:
        # Use the contact-specific hook, cleaned up for email tone
        hook = contact_hook
        # Strip any leading quotes
        hook = hook.strip('"').strip("'").strip()
    elif district_hook:
        hook = district_hook
    else:
        hook = (
            f"We came across {short_name}'s STEM initiatives and thought "
            f"our platform could be a great fit for your students. We think "
            f"we have the type of program that your students will certainly "
            f"be able to benefit from."
        )

    # Ensure we/us pronouns throughout (never I/me)
    hook = hook.replace(" I ", " we ").replace(" my ", " our ").replace(" me ", " us ")
    hook = hook.replace('"', "").replace("'s ", "'s ")

    subject_encoded = urllib.parse.quote(f"Preview Account Request - {short_name}")
    body_encoded = urllib.parse.quote(
        "Hi Dr. Martin,\n\nWe'd like to request a free teacher preview account.\n\nThank you!"
    )
    mailto = f"mailto:{FROM_EMAIL}?subject={subject_encoded}&body={body_encoded}"

    html = f"""<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
<p>Dear {first_name},</p>

<p>{hook}</p>

<p>We have a company called <a href="https://modelitk12.com/#/" style="color: #2997FF;">ModelIt</a> &mdash; an NSF SBIR-funded platform where students design, build, and run computational models (ecosystems, pollution cycles, population dynamics) right in the classroom. It's NGSS-aligned and works alongside your existing curriculum, not instead of it.</p>

<p>We have science lessons live on the platform right now. We can set up a <b>free teacher preview account</b> so you and your team can explore it firsthand &mdash; no commitment, just a chance to see if it fits your STEM goals.</p>

<p><b>A glimpse of ModelIt in action</b></p>

<p><a href="https://modelitk12.com/#/"><img src="{SCREENSHOT_BUILD}" alt="ModelIt - Students building computational models in the classroom" style="max-width: 500px; width: 100%; border: 1px solid #ddd; border-radius: 4px;" /></a><br/><b>Build it:</b> Students connect real-world components to construct scientific models step by step</p>

<p><a href="https://modelitk12.com/#/"><img src="{SCREENSHOT_RUN}" alt="ModelIt - Science simulation platform" style="max-width: 500px; width: 100%; border: 1px solid #ddd; border-radius: 4px;" /></a><br/><b>Run it:</b> Watch the model come to life with real-time data and interactive graphs</p>

<p>We're also building <b>MicroMayhem</b> &mdash; a game where students battle real biological threats using the same modeling skills they learn in class. Students love it because it feels like a video game. Teachers love it because every move reinforces real science. Here's a sneak peek:</p>

<p><a href="{MICROMAYHEM_VIDEO}">&#9654; <b>Watch the MicroMayhem Preview (30 sec)</b></a></p>

<p style="text-align: center; margin: 20px 0;"><a href="{mailto}" style="background-color: #2997FF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Reply "Preview" for Free Access</a></p>

<p>Or let us know if you'd like to hop on a quick call to discuss.</p>

<br/><p style="margin: 0;">Kind regards,</p><br/>

<p style="margin: 0;"><b>Dr. Marie Martin &amp; Dr. Charles Martin</b></p>
<p style="margin: 0;">Discovery Collective / <a href="https://modelitk12.com/#/" style="color: #2997FF;">ModelIt</a></p>
<p style="margin: 0;"><a href="mailto:{FROM_EMAIL}" style="color: #2997FF;">Email</a> &middot; <a href="https://modelitk12.com/#/" style="color: #2997FF;">modelitk12.com</a></p>
<p style="margin: 0; font-size: 12px; color: #888;">NSF SBIR Phase II Funded | NGSS-Aligned | K-12 Computational Modeling</p>
</body></html>"""
    return html


def send_email(to_email, subject, html_body):
    """Send email via gogcli with inline HTML."""
    tmp_file = Path("/tmp/modelit-email.html")
    tmp_file.write_text(html_body, encoding="utf-8")

    cmd = (
        f"gog gmail send --client {GOG_CLIENT} "
        f'--account {FROM_EMAIL} '
        f'--to "{to_email}" '
        f'--subject "{subject}" '
        f'--body-html "$(cat /tmp/modelit-email.html)"'
    )

    result = run_cmd(cmd, check=False)
    tmp_file.unlink(missing_ok=True)

    if result.returncode == 0:
        return True, result.stdout.strip()
    else:
        return False, result.stderr.strip()


def create_hubspot_contact(contact, district_name):
    """Create a HubSpot contact."""
    if not HUBSPOT_TOKEN:
        return None
    parts = contact["name"].split() if contact.get("name") else [""]
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    data = {
        "properties": {
            "email": contact["email"],
            "firstname": first_name,
            "lastname": last_name,
            "jobtitle": contact.get("title", ""),
            "company": district_name,
            "contact_segment": "leadership",
            "lead_temperature": "warm",
            "contact_attempt": "1",
        }
    }

    result = hubspot_request("POST", "/crm/v3/objects/contacts", data)
    if result and "id" in result:
        print(f"    HubSpot contact created: {result['id']}")
        return result["id"]
    elif result and "already exists" in str(result).lower():
        print(f"    HubSpot contact already exists")
        search_data = {
            "filterGroups": [
                {"filters": [{"propertyName": "email", "operator": "EQ", "value": contact["email"]}]}
            ]
        }
        search_result = hubspot_request("POST", "/crm/v3/objects/contacts/search", search_data)
        if search_result and search_result.get("results"):
            return search_result["results"][0]["id"]
    return None


def create_hubspot_deal(district_name, contact_id, amount=15000):
    """Create one HubSpot deal per district."""
    if not HUBSPOT_TOKEN:
        return None
    data = {
        "properties": {
            "dealname": f"{district_name} - ModelIt K12 Pilot",
            "dealstage": "appointmentscheduled",
            "amount": str(amount),
            "pipeline": "default",
        }
    }

    result = hubspot_request("POST", "/crm/v3/objects/deals", data)
    if result and "id" in result:
        deal_id = result["id"]
        print(f"    HubSpot deal created: {deal_id}")
        if contact_id:
            assoc_data = [
                {
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
                }
            ]
            hubspot_request("PUT", f"/crm/v4/objects/deals/{deal_id}/associations/contacts", assoc_data)
        return deal_id
    return None


def log_email_hubspot(contact_id, subject, html_body):
    """Log sent email in HubSpot."""
    if not HUBSPOT_TOKEN or not contact_id:
        return
    data = {
        "properties": {
            "hs_email_direction": "EMAIL",
            "hs_email_status": "SENT",
            "hs_email_subject": subject,
            "hs_email_text": html_body[:5000],
            "hs_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }
    result = hubspot_request("POST", "/crm/v3/objects/emails", data)
    if result and "id" in result:
        email_id = result["id"]
        assoc_data = [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 198}],
            }
        ]
        hubspot_request("PUT", f"/crm/v4/objects/emails/{email_id}/associations/contacts", assoc_data)
        print(f"    HubSpot email logged: {email_id}")


def send_telegram(message):
    """Send a message to the ModelIt LCAP Agent Telegram group."""
    cmd = f'openclaw send --to "{TELEGRAM_GROUP}" --message "{message}"'
    run_cmd(cmd, check=False)


def process_district(district_name, slug, args):
    """Process a single district: send emails to ALL contacts at once."""
    print(f"\n{'='*60}")
    print(f"  {district_name}")
    print(f"{'='*60}")

    contacts = parse_all_contacts(slug)
    if not contacts:
        print(f"  SKIP: No contacts found in districts/{slug}/contacts.md")
        return 0, 1

    hook = parse_district_hook(slug)
    short_name = shorten_district(district_name)
    subject = f"A quick look at computational modeling for {clean_district_name(short_name)} science"

    print(f"  Found {len(contacts)} contacts with emails")
    print(f"  Subject: {subject}")
    print(f"  Sending from: {FROM_EMAIL}")

    sent_count = 0
    failed_count = 0
    deal_id = None

    for i, contact in enumerate(contacts, 1):
        print(f"\n  [{i}/{len(contacts)}] {contact['name']} <{contact['email']}> - {contact.get('title', 'N/A')}")

        html_body = build_email_html(district_name, contact, district_hook=hook)

        if args.dry_run:
            print(f"    DRY RUN: Would send to {contact['email']}")
            sent_count += 1
            continue

        # HubSpot sync
        contact_id = None
        if not args.skip_hubspot:
            contact_id = create_hubspot_contact(contact, district_name)
            if deal_id is None:
                deal_id = create_hubspot_deal(district_name, contact_id)
            elif contact_id:
                assoc_data = [
                    {
                        "to": {"id": contact_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
                    }
                ]
                hubspot_request("PUT", f"/crm/v4/objects/deals/{deal_id}/associations/contacts", assoc_data)

        # Send email
        success, msg_info = send_email(contact["email"], subject, html_body)
        if success:
            print(f"    Email SENT")
            sent_count += 1

            if not args.skip_hubspot and contact_id:
                log_email_hubspot(contact_id, subject, html_body)

            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "district": district_name,
                "contact_name": contact.get("name", ""),
                "contact_title": contact.get("title", ""),
                "contact_email": contact["email"],
                "subject": subject,
                "hubspot_contact_id": contact_id,
                "hubspot_deal_id": deal_id,
                "status": "sent",
            }
            with open(OUTREACH_LOG, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        else:
            print(f"    FAILED: {msg_info}")
            failed_count += 1

    print(f"\n  District summary: {sent_count} sent, {failed_count} failed")
    return sent_count, failed_count


def main():
    parser = argparse.ArgumentParser(description="ModelIt district outreach - send to ALL contacts at once")
    parser.add_argument("--batch", type=int, default=10, help="Number of districts to process")
    parser.add_argument("--district", type=str, help="Single district slug (e.g., carlsbad-usd)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--skip-hubspot", action="store_true", help="Skip HubSpot sync")
    args = parser.parse_args()

    if args.district:
        district_slug = args.district
        district_name = district_slug.replace("-", " ").title()
        if DATA_FILE.exists():
            with open(DATA_FILE) as f:
                districts = json.load(f)
            for d in districts:
                s = d["name"].lower().replace(" ", "-").replace(".", "").replace("'", "")
                if s == district_slug:
                    district_name = d["name"]
                    break
        sent, failed = process_district(district_name, district_slug, args)
        summary = f"ModelIt Outreach: {district_name} - {sent} emails sent, {failed} failed"
        print(f"\n{summary}")
        if not args.dry_run:
            send_telegram(summary)
        return

    # Batch mode
    if not DATA_FILE.exists():
        print("ERROR: data/cde-districts.json not found")
        sys.exit(1)

    with open(DATA_FILE) as f:
        districts = json.load(f)

    ready = [d for d in districts if d["status"] == "researched"][: args.batch]

    if not ready:
        print("No researched districts ready for outreach.")
        return

    print(f"Outreach batch: {len(ready)} districts")
    total_sent = 0
    total_failed = 0

    for d in ready:
        district_name = d["name"]
        slug = district_name.lower().replace(" ", "-").replace(".", "").replace("'", "")
        sent, failed = process_district(district_name, slug, args)
        total_sent += sent
        total_failed += failed

        if sent > 0:
            for dd in districts:
                if dd["name"] == district_name:
                    dd["status"] = "contacted"
                    break

    with open(DATA_FILE, "w") as f:
        json.dump(districts, f, indent=2, ensure_ascii=False)

    summary = f"ModelIt Outreach Complete: {total_sent} emails sent across {len(ready)} districts ({total_failed} failed)"
    print(f"\n{summary}")
    send_telegram(summary)


if __name__ == "__main__":
    main()
