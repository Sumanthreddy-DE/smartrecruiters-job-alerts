import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

# ── Config ──────────────────────────────────────────────────────────
CONFIG = {
    "company": "BoschGroup",
    "country": "de",
    "city": "Reutlingen",
    "hours_window": 72,
    "experience_levels": ["internship", "entry_level", "associate", "not_applicable"],
    "keywords": [],  # empty = all jobs | future: ["software", "data", "embedded"]
}

API_BASE = "https://api.smartrecruiters.com/v1/companies"
JOB_LINK = "https://jobs.smartrecruiters.com/BoschGroup"


# ── Fetch ───────────────────────────────────────────────────────────
def fetch_jobs():
    url = f"{API_BASE}/{CONFIG['company']}/postings"
    params = {
        "country": CONFIG["country"],
        "city": CONFIG["city"],
        "limit": 100,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("content", [])


# ── Filter ──────────────────────────────────────────────────────────
def filter_jobs(jobs):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CONFIG["hours_window"])
    allowed_levels = set(CONFIG["experience_levels"])
    keywords = [k.lower() for k in CONFIG["keywords"]]

    filtered = []
    for job in jobs:
        # Experience level check
        level = job.get("experienceLevel", {}).get("id", "")
        if level not in allowed_levels:
            continue

        # Date check
        released = job.get("releasedDate", "")
        if not released:
            continue
        try:
            released_dt = datetime.fromisoformat(released.replace("Z", "+00:00"))
        except ValueError:
            continue
        if released_dt < cutoff:
            continue

        # Keyword check (skip if no keywords configured)
        if keywords:
            title = job.get("name", "").lower()
            if not any(kw in title for kw in keywords):
                continue

        filtered.append(job)

    return sorted(filtered, key=lambda j: j.get("releasedDate", ""), reverse=True)


# ── Build job link ──────────────────────────────────────────────────
def job_url(job):
    posting_id = job.get("id", "")
    return f"{JOB_LINK}/{posting_id}"


# ── Email ───────────────────────────────────────────────────────────
def build_email_html(jobs):
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")

    if not jobs:
        return f"""
        <h2>Bosch Reutlingen — No new jobs</h2>
        <p>No new student/graduate jobs posted in the last {CONFIG['hours_window']} hours.</p>
        <p style="color:#888; font-size:12px;">Checked on {today}</p>
        """

    rows = ""
    for job in jobs:
        name = job.get("name", "Unknown")
        date = job.get("releasedDate", "")[:10]
        level = job.get("experienceLevel", {}).get("label", "")
        link = job_url(job)

        rows += f"""
        <tr>
            <td style="padding:8px; border-bottom:1px solid #eee;">
                <a href="{link}" style="color:#1a73e8; text-decoration:none; font-weight:bold;">{name}</a>
            </td>
            <td style="padding:8px; border-bottom:1px solid #eee;">{level}</td>
            <td style="padding:8px; border-bottom:1px solid #eee;">{date}</td>
        </tr>"""

    return f"""
    <h2>Bosch Reutlingen — {len(jobs)} new job{"s" if len(jobs) != 1 else ""}</h2>
    <table style="border-collapse:collapse; width:100%; font-family:Arial,sans-serif; font-size:14px;">
        <tr style="background:#f5f5f5;">
            <th style="padding:8px; text-align:left;">Job Title</th>
            <th style="padding:8px; text-align:left;">Level</th>
            <th style="padding:8px; text-align:left;">Posted</th>
        </tr>
        {rows}
    </table>
    <p style="color:#888; font-size:12px; margin-top:16px;">
        Checked on {today} | Showing jobs from the last {CONFIG['hours_window']} hours
    </p>
    """


def send_email(html, job_count):
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        print("ERROR: GMAIL_ADDRESS and GMAIL_APP_PASSWORD env vars required")
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%b %d")
    subject = f"Bosch Reutlingen — {job_count} new job{'s' if job_count != 1 else ''} ({today})"
    if job_count == 0:
        subject = f"Bosch Reutlingen — No new jobs ({today})"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.send_message(msg)

    print(f"Email sent: {subject}")


# ── Main ────────────────────────────────────────────────────────────
def main():
    print("Fetching Bosch Reutlingen jobs...")
    jobs = fetch_jobs()
    print(f"Found {len(jobs)} total jobs")

    filtered = filter_jobs(jobs)
    print(f"After filtering: {len(filtered)} jobs in last {CONFIG['hours_window']}h")

    html = build_email_html(filtered)
    send_email(html, len(filtered))


if __name__ == "__main__":
    main()
