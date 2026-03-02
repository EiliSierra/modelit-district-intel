#!/usr/bin/env python3
"""
ModelIt Batch Outreach — 5-Day Email Campaign
Reads ALL contacts from researched districts, splits into 5 nightly batches,
sends personalized emails with 5-minute delays between each.

Usage:
  python3 modelit-batch-send.py --day 1          # Send night 1 batch
  python3 modelit-batch-send.py --day 1 --dry-run # Preview without sending
  python3 modelit-batch-send.py --list            # Show batch breakdown
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_DIR / "data" / "cde-districts.json"
OUTREACH_LOG = REPO_DIR / "data" / "outreach-log.jsonl"
DISTRICTS_DIR = REPO_DIR / "districts"

# Email config
FROM_EMAIL = "charles@discoverycollective.com"
GOG_CLIENT = "dc"
GOG_KEYRING_PASSWORD = os.environ.get("GOG_KEYRING_PASSWORD", "openclaw2026")

# HubSpot
HUBSPOT_TOKEN = os.environ.get("HUBSPOT_TOKEN", "")

# Telegram
TELEGRAM_GROUP = os.environ.get("TELEGRAM_GROUP", "-5188258108")

# Email assets
SCREENSHOT_URL = "https://raw.githubusercontent.com/charlesmartinedd/modelit-district-intel/main/_reference/email-assets/modelit-platform.png"
STUDENT_URL = "https://raw.githubusercontent.com/charlesmartinedd/modelit-district-intel/main/_reference/email-assets/modelit-student.png"

# Delay between emails (seconds)
SEND_DELAY = 300  # 5 minutes

# Number of batches
NUM_BATCHES = 5


def run_cmd(cmd, check=False):
    """Run a shell command."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"CMD FAILED: {cmd}\n{result.stderr}")
    return result


def load_already_sent():
    """Load set of already-sent email addresses from outreach log."""
    sent = set()
    if OUTREACH_LOG.exists():
        for line in OUTREACH_LOG.read_text(encoding='utf-8', errors='replace').strip().split('\n'):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("status") == "sent":
                    sent.add(entry.get("contact_email", "").lower())
            except json.JSONDecodeError:
                pass
    return sent


def clean_email(raw):
    """Extract clean email from a cell that may have backticks, notes, etc."""
    # Remove backticks
    raw = raw.replace('`', '')
    # Find first email-like pattern
    m = re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', raw)
    if not m:
        return None
    email = m.group(0).lower()
    # Skip TBD or placeholder emails
    if 'tbd' in email or 'example' in email:
        return None
    return email


def parse_contacts_md(district_slug):
    """Parse contacts.md to extract all contacts with valid emails.

    Handles two formats:
    A) Columnar tables: | # | **Name** | Title | Email | ... |
    B) Per-section: ### Name — Title\\n| Email | addr@domain |
       with optional | Title | ... | and | Pitch Hook | ... | rows
    """
    path = DISTRICTS_DIR / district_slug / "contacts.md"
    if not path.exists():
        return []

    content = path.read_text(encoding='utf-8', errors='replace')
    lines = content.split('\n')
    contacts = []
    seen_emails = set()

    # --- Strategy: Walk lines, tracking current section header ---
    current_name = None
    current_title = None
    current_hook = None
    current_email = None

    def flush_contact():
        nonlocal current_name, current_title, current_hook, current_email
        if current_email and current_email not in seen_emails:
            seen_emails.add(current_email)
            contacts.append({
                'email': current_email,
                'name': current_name or current_email.split('@')[0].replace('.', ' ').title(),
                'title': current_title or '',
                'pitch_hook': current_hook or '',
                'district_slug': district_slug
            })
        current_name = None
        current_title = None
        current_hook = None
        current_email = None

    for line in lines:
        stripped = line.strip()

        # --- Format B/C: ### Name — Title headers ---
        # "### Dr. Jerry Gargus, Ed.D. — Assistant Superintendent, Educational Services"
        # "### 1. Tammy Barrera — Assistant Superintendent (Curriculum & Instruction)"
        if stripped.startswith('### '):
            flush_contact()
            header = stripped[4:].strip()
            # Remove leading number + dot (e.g., "1. ")
            header = re.sub(r'^\d+\.\s*', '', header)
            # Split on em-dash or double hyphen
            parts = re.split(r'\s*[—–]\s*|\s+-\s+', header, maxsplit=1)
            current_name = parts[0].strip().rstrip(',')
            # Clean name: remove credentials and board info
            current_name = re.sub(r',?\s*(?:Ed\.?D\.?|Ph\.?D\.?|M\.?A\.?|M\.?Ed\.?|J\.?D\.?)\s*$', '', current_name, flags=re.I).strip()
            if len(parts) > 1:
                current_title = parts[1].strip()
            continue

        # --- Format C: Bullet-list contact details ---
        # "- **Email:** tbarrera@beardsley.k12.ca.us emoji"
        if stripped.startswith('- **Email') or stripped.startswith('- **E-mail'):
            email = clean_email(stripped)
            if email:
                current_email = email
            continue

        # "- **Phone:**", "- **Background:**", "- **Why:**" — skip
        if stripped.startswith('- **') and not stripped.startswith('- **Email'):
            continue

        # --- Table rows ---
        if '|' not in stripped or stripped.startswith('|--') or stripped.startswith('| --'):
            continue

        cells = [c.strip() for c in stripped.split('|')]
        cells = [c for c in cells if c]  # Remove empty strings from leading/trailing |

        if len(cells) < 2:
            continue

        # --- Format B: Key-value rows (| Field | Value |) ---
        if len(cells) == 2:
            key = cells[0].lower().strip()
            val = cells[1].strip()

            if key in ('email', 'e-mail'):
                email = clean_email(val)
                if email:
                    current_email = email

            elif key == 'title':
                if not current_title:
                    current_title = re.sub(r'\*\*(.+?)\*\*', r'\1', val).strip()

            elif key == 'name':
                if not current_name:
                    current_name = re.sub(r'\*\*(.+?)\*\*', r'\1', val).strip()

            elif key in ('pitch hook', 'hook'):
                current_hook = re.sub(r'"(.+?)"', r'\1', val).strip()

            continue

        # --- Format A: Columnar tables (| # | **Name** | Title | Email | ... |) ---
        # Look for an email in any cell
        row_email = None
        row_name = None
        row_title = None

        for cell in cells:
            if not row_email:
                email = clean_email(cell)
                if email:
                    row_email = email

            if not row_name:
                bold = re.search(r'\*\*(.+?)\*\*', cell)
                if bold:
                    candidate = bold.group(1).strip()
                    # Exclude non-name bold text
                    if not any(kw in candidate.lower() for kw in [
                        'top', 'high', 'medium', 'low', 'primary', 'yes', 'no',
                        'email', 'phone', 'title', 'field', 'value', 'tier',
                        'confirmed', 'inferred', 'pattern'
                    ]):
                        row_name = candidate

            if not row_title:
                cell_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', cell).strip()
                if any(kw in cell_clean.lower() for kw in [
                    'director', 'superintendent', 'principal', 'coordinator',
                    'specialist', 'officer', 'manager', 'chief', 'assistant',
                    'president', 'board', 'tosa', 'admin', 'curriculum',
                    'trustee', 'member', 'clerk', 'secretary', 'lead',
                    'counselor', 'teacher', 'coach', 'nurse', 'librarian'
                ]):
                    if len(cell_clean) > 5:
                        row_title = cell_clean

        if row_email and row_email not in seen_emails:
            seen_emails.add(row_email)
            contacts.append({
                'email': row_email,
                'name': row_name or row_email.split('@')[0].replace('.', ' ').title(),
                'title': row_title or '',
                'pitch_hook': '',
                'district_slug': district_slug
            })

    # Flush last section contact
    flush_contact()

    return contacts


def parse_hook(district_slug):
    """Extract the district hook/pitch from entry-strategy.md."""
    path = DISTRICTS_DIR / district_slug / "entry-strategy.md"
    if not path.exists():
        return None

    content = path.read_text(encoding='utf-8', errors='replace')

    # Format 1: ## The Hook with blockquote
    hook_match = re.search(r'## The Hook\s*\n\n> "(.+?)"', content, re.DOTALL)
    if hook_match:
        hook = hook_match.group(1).strip().replace('\n> ', ' ')
        return hook

    # Format 2: ## Key Messages by Audience — grab first message block
    key_msgs = re.search(
        r'## Key Messages by Audience\s*\n.*?\n- (.+?)(?:\n-|\n\n|$)',
        content, re.DOTALL
    )
    if key_msgs:
        first_msg = key_msgs.group(1).strip()
        # Clean up markdown formatting
        first_msg = re.sub(r'"(.+?)"', r'\1', first_msg)
        return first_msg

    # Format 3: ## Why {district} — grab the summary table signals
    why_match = re.search(r'## Why .+?\n\n\|.*?\n\|.*?\n((?:\|.*?\n)+)', content)
    if why_match:
        signals = []
        for line in why_match.group(1).strip().split('\n')[:3]:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                signals.append(parts[1].replace('**', ''))
        if signals:
            return '; '.join(signals)

    return None


def get_district_name(slug, districts_data):
    """Get the full district name from cde-districts.json."""
    for d in districts_data:
        d_slug = d['name'].lower().replace(' ', '-').replace('.', '').replace("'", '')
        if d_slug == slug or slug.startswith(d_slug[:10]):
            return d['name']
    # Fallback: convert slug to title case
    return slug.replace('-', ' ').title()


def build_email_html(district_name, contact, hook):
    """Build personalized HTML email."""
    first_name = contact['name'].split()[0] if contact.get('name') else 'there'

    # Use per-contact pitch hook if available, else district-level hook
    if contact.get('pitch_hook'):
        hook = contact['pitch_hook']

    # Default hook if none found
    if not hook:
        hook = (f"I noticed {district_name} has some exciting STEM initiatives, "
                f"and I wanted to share something that might complement your work.")

    # Trim hook to 2-3 sentences
    sentences = hook.split('. ')
    if len(sentences) > 3:
        hook = '. '.join(sentences[:3]) + '.'

    # Clean up any leftover markdown
    hook = re.sub(r'\*\*(.+?)\*\*', r'\1', hook)
    hook = hook.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Personalize based on title if available
    title_note = ""
    if contact.get('title'):
        title_lower = contact['title'].lower()
        if any(kw in title_lower for kw in ['principal', 'school']):
            title_note = "As a school leader, you're in a great position to see how this could work in your classrooms. "
        elif any(kw in title_lower for kw in ['board', 'trustee', 'president']):
            title_note = "As a board member, you're shaping the strategic direction for student outcomes. "
        elif any(kw in title_lower for kw in ['superintendent']):
            title_note = "Given your role leading the district, I wanted to make sure this was on your radar. "
        elif any(kw in title_lower for kw in ['technology', 'cto', 'it ']):
            title_note = "From a technology standpoint, ModelIt integrates with your existing LMS and SSO. "

    district_short = (district_name
                      .replace(' Unified', '')
                      .replace(' Elementary', '')
                      .replace(' School District', '')
                      .replace(' Union', ''))

    html = f"""<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
<p>Hi {first_name},</p>

<p>{hook}</p>

<p>{title_note}ModelIt is a computational modeling platform for K-12 that lets students build, test, and explore scientific models &mdash; no coding required. It directly addresses NGSS Science and Engineering Practices and has shown measurable improvement in CAST preparation.</p>

<p><img src="{SCREENSHOT_URL}" alt="ModelIt Platform" style="max-width: 500px; border: 1px solid #ddd; border-radius: 4px;" /></p>

<p>If this looks like something worth exploring for {district_short}, just reply &ldquo;preview&rdquo; and I&rsquo;ll send over a hands-on demo link.</p>

<p>Best,<br/>
Dr. Charles Martin &amp; Dr. Marie Martin<br/>
Discovery Collective / ModelIt<br/>
<a href="mailto:{FROM_EMAIL}">{FROM_EMAIL}</a><br/>
(323) 632-0271</p>
</body></html>"""
    return html


def send_email(to_email, subject, html_body):
    """Send email via gogcli."""
    tmp_file = Path("/tmp/modelit-batch-email.html")
    tmp_file.write_text(html_body, encoding='utf-8')

    cmd = (f'GOG_KEYRING_PASSWORD={GOG_KEYRING_PASSWORD} '
           f'gog gmail send --client {GOG_CLIENT} '
           f'--account {FROM_EMAIL} '
           f'--to "{to_email}" '
           f'--subject "{subject}" '
           f'--body-html-file "{tmp_file}"')

    result = run_cmd(cmd, check=False)
    tmp_file.unlink(missing_ok=True)

    if result.returncode == 0:
        msg_id = ""
        for line in result.stdout.split('\n'):
            if 'message_id' in line or 'id' in line.lower():
                msg_id = line.strip()
                break
        return True, msg_id
    else:
        return False, result.stderr[:200]


def hubspot_create_contact(contact, district_name):
    """Create/find HubSpot contact. Returns contact_id or None."""
    if not HUBSPOT_TOKEN:
        return None

    import urllib.request
    first_name = contact['name'].split()[0] if contact.get('name') else ''
    last_name = ' '.join(contact['name'].split()[1:]) if contact.get('name') and len(contact['name'].split()) > 1 else ''

    data = {
        "properties": {
            "email": contact['email'],
            "firstname": first_name,
            "lastname": last_name,
            "jobtitle": contact.get('title', ''),
            "company": district_name,
            "contact_segment": "leadership",
            "lead_temperature": "warm"
        }
    }

    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {HUBSPOT_TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data).encode()

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return result.get('id')
    except urllib.error.HTTPError as e:
        if e.code == 409:  # Conflict — already exists
            # Search for existing
            search_url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
            search_data = {"filterGroups": [{"filters": [
                {"propertyName": "email", "operator": "EQ", "value": contact['email']}
            ]}]}
            req2 = urllib.request.Request(search_url, method="POST")
            req2.add_header("Authorization", f"Bearer {HUBSPOT_TOKEN}")
            req2.add_header("Content-Type", "application/json")
            req2.data = json.dumps(search_data).encode()
            try:
                with urllib.request.urlopen(req2) as resp2:
                    result2 = json.loads(resp2.read())
                    if result2.get('results'):
                        return result2['results'][0]['id']
            except Exception:
                pass
        return None
    except Exception:
        return None


def send_telegram(message):
    """Send Telegram notification."""
    # Escape special chars for Telegram
    cmd = f'openclaw send --to "{TELEGRAM_GROUP}" --message "{message[:4000]}"'
    run_cmd(cmd, check=False)


def build_send_queue(districts_data):
    """Build the full send queue from all researched districts."""
    already_sent = load_already_sent()
    queue = []

    # Get all district slugs that have contacts
    researched = [d for d in districts_data if d.get('status') == 'researched']

    for d in researched:
        district_name = d['name']
        slug = district_name.lower().replace(' ', '-').replace('.', '').replace("'", '')

        # Find matching directory (slug might not match exactly)
        matching_dir = None
        for dirname in os.listdir(DISTRICTS_DIR):
            if not (DISTRICTS_DIR / dirname).is_dir():
                continue
            # Try exact match or partial match
            if dirname == slug or dirname.startswith(slug[:8]):
                matching_dir = dirname
                break

        if not matching_dir:
            # Try reverse: check if district name matches directory
            for dirname in os.listdir(DISTRICTS_DIR):
                if not (DISTRICTS_DIR / dirname).is_dir():
                    continue
                dir_words = set(dirname.replace('-', ' ').lower().split())
                name_words = set(district_name.lower().split())
                if len(dir_words & name_words) >= 2:
                    matching_dir = dirname
                    break

        if not matching_dir:
            print(f"  SKIP: No directory found for '{district_name}' (tried slug: {slug})")
            continue

        # Parse contacts
        contacts = parse_contacts_md(matching_dir)
        if not contacts:
            print(f"  SKIP: No contacts found for {matching_dir}")
            continue

        # Parse hook
        hook = parse_hook(matching_dir)

        # Filter out already-sent contacts
        for c in contacts:
            if c['email'].lower() in already_sent:
                continue
            queue.append({
                'district_name': district_name,
                'district_slug': matching_dir,
                'contact': c,
                'hook': hook
            })

    return queue


def split_batches(queue, num_batches=NUM_BATCHES):
    """Split queue into batches, keeping districts together."""
    # Group by district
    by_district = {}
    for item in queue:
        key = item['district_slug']
        if key not in by_district:
            by_district[key] = []
        by_district[key].append(item)

    # Sort districts by size (largest first) for even distribution
    district_groups = sorted(by_district.values(), key=len, reverse=True)

    # Distribute districts across batches (greedy bin packing)
    batches = [[] for _ in range(num_batches)]
    batch_sizes = [0] * num_batches

    for group in district_groups:
        # Put this district group in the smallest batch
        min_idx = batch_sizes.index(min(batch_sizes))
        batches[min_idx].extend(group)
        batch_sizes[min_idx] += len(group)

    return batches


def main():
    parser = argparse.ArgumentParser(description="ModelIt 5-Day Batch Email Campaign")
    parser.add_argument("--day", type=int, choices=[1, 2, 3, 4, 5],
                        help="Which day's batch to send (1-5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without sending")
    parser.add_argument("--list", action="store_true",
                        help="Show batch breakdown without sending")
    parser.add_argument("--no-hubspot", action="store_true",
                        help="Skip HubSpot sync")
    parser.add_argument("--delay", type=int, default=SEND_DELAY,
                        help=f"Seconds between emails (default: {SEND_DELAY})")
    args = parser.parse_args()

    if not args.day and not args.list:
        parser.error("Either --day N or --list is required")

    # Load districts
    with open(DATA_FILE, encoding='utf-8') as f:
        districts_data = json.load(f)

    print(f"Building send queue from {len([d for d in districts_data if d.get('status') == 'researched'])} researched districts...")
    queue = build_send_queue(districts_data)
    print(f"Total sendable contacts: {len(queue)}")

    if len(queue) == 0:
        print("No contacts to send. Check district statuses and contacts.md files.")
        return

    # Split into batches
    batches = split_batches(queue)

    # Show batch breakdown
    if args.list or args.dry_run:
        print(f"\n{'='*60}")
        print(f"BATCH BREAKDOWN ({NUM_BATCHES} nights)")
        print(f"{'='*60}")
        for i, batch in enumerate(batches, 1):
            districts_in_batch = {}
            for item in batch:
                dn = item['district_name']
                districts_in_batch[dn] = districts_in_batch.get(dn, 0) + 1
            print(f"\nNight {i}: {len(batch)} emails")
            runtime_hrs = len(batch) * args.delay / 3600
            print(f"  Est. runtime: {runtime_hrs:.1f} hours")
            for dn, count in sorted(districts_in_batch.items()):
                print(f"  - {dn}: {count} contacts")

        if args.list:
            return

    # Send a specific day's batch
    day_idx = args.day - 1
    batch = batches[day_idx]

    if not batch:
        print(f"Night {args.day}: No emails to send.")
        return

    print(f"\n{'='*60}")
    print(f"NIGHT {args.day}: Sending {len(batch)} emails")
    print(f"Delay: {args.delay}s between emails")
    est_hours = len(batch) * args.delay / 3600
    print(f"Est. runtime: {est_hours:.1f} hours")
    print(f"{'='*60}\n")

    sent_count = 0
    failed_count = 0
    skipped_count = 0
    districts_contacted = set()

    for i, item in enumerate(batch, 1):
        district_name = item['district_name']
        contact = item['contact']
        hook = item['hook']

        district_short = (district_name
                          .replace(' Unified', '')
                          .replace(' Elementary', '')
                          .replace(' School District', '')
                          .replace(' Union', ''))

        subject = f"A quick look at computational modeling for {district_short} science"
        html_body = build_email_html(district_name, contact, hook)

        print(f"[{i}/{len(batch)}] {contact['name']} <{contact['email']}> ({district_name})")

        if args.dry_run:
            print(f"  DRY RUN: Would send — Subject: {subject[:60]}...")
            if hook:
                print(f"  Hook: {hook[:80]}...")
            sent_count += 1
            districts_contacted.add(item['district_slug'])
            continue

        # Send email
        success, msg_info = send_email(contact['email'], subject, html_body)

        if success:
            print(f"  SENT ({msg_info})")
            sent_count += 1
            districts_contacted.add(item['district_slug'])

            # Log to outreach-log.jsonl
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "batch_day": args.day,
                "district": district_name,
                "district_slug": item['district_slug'],
                "contact_name": contact.get('name', ''),
                "contact_email": contact['email'],
                "contact_title": contact.get('title', ''),
                "subject": subject,
                "status": "sent"
            }

            # HubSpot sync
            if not args.no_hubspot and HUBSPOT_TOKEN:
                contact_id = hubspot_create_contact(contact, district_name)
                if contact_id:
                    log_entry["hubspot_contact_id"] = contact_id

            with open(OUTREACH_LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')

        else:
            print(f"  FAILED: {msg_info}")
            failed_count += 1

            # Log failure
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "batch_day": args.day,
                "district": district_name,
                "district_slug": item['district_slug'],
                "contact_name": contact.get('name', ''),
                "contact_email": contact['email'],
                "subject": subject,
                "status": "failed",
                "error": msg_info[:200]
            }
            with open(OUTREACH_LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')

        # Wait between emails (skip delay after last email)
        if i < len(batch) and not args.dry_run:
            print(f"  Waiting {args.delay}s...")
            time.sleep(args.delay)

    # Update district statuses to 'contacted' for fully-sent districts
    if not args.dry_run:
        already_sent = load_already_sent()
        for d in districts_data:
            if d.get('status') != 'researched':
                continue
            slug = d['name'].lower().replace(' ', '-').replace('.', '').replace("'", '')
            # Check if slug matches any contacted district
            for contacted_slug in districts_contacted:
                if contacted_slug.startswith(slug[:8]) or slug.startswith(contacted_slug[:8]):
                    # Check if ALL contacts in this district have been sent
                    district_contacts = parse_contacts_md(contacted_slug)
                    all_sent = all(c['email'].lower() in already_sent for c in district_contacts)
                    if all_sent:
                        d['status'] = 'contacted'
                        print(f"\nUpdated {d['name']} status -> contacted")

        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(districts_data, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'='*60}")
    print(f"NIGHT {args.day} COMPLETE")
    print(f"  Sent: {sent_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Districts touched: {len(districts_contacted)}")
    print(f"{'='*60}")

    # Send Telegram summary
    if not args.dry_run:
        tg_msg = (f"ModelIt Batch Night {args.day} Complete\\n"
                  f"Sent: {sent_count} | Failed: {failed_count}\\n"
                  f"Districts: {', '.join(sorted(districts_contacted))}")
        send_telegram(tg_msg)


if __name__ == "__main__":
    main()
