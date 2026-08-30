#!/usr/bin/env python3
"""
Tax Receipt Finder for Gmail
-----------------------------
Connects to Gmail accounts (wendy.park2003@gmail.com & wendy.park1001@gmail.com),
searches for all tax invoices, receipts, bills, and purchase confirmations for the
financial year, downloads attachments/emails, and generates a summary CSV.

Usage:
  python3 fetch_tax_receipts.py
"""

import os
import sys
import getpass
import imaplib
import email
from email.header import decode_header
import re
import csv
from datetime import datetime
from pathlib import Path

# Default Accounts to process
ACCOUNTS = [
    "wendy.park2003@gmail.com",
    "wendy.park1001@gmail.com",
]

# Date range for Australian FY 2025-2026 (1 July 2025 to 30 June 2026)
SINCE_DATE = "01-Jul-2025"
BEFORE_DATE = "01-Jul-2026"

OUTPUT_DIR = Path("tax_receipts_fy2025_2026")

KEYWORDS = [
    "receipt",
    "tax invoice",
    "invoice",
    "order confirmation",
    "payment confirmation",
    "payment received",
    "subscription",
    "statement",
    "bill",
    "donation",
    "officeworks",
    "apple",
    "google",
    "amazon",
    "uber",
    "bunnings",
    "jbhifi",
    "jb hi-fi",
    "adobe",
    "microsoft",
    "zoom",
    "notion",
    "canva",
    "github",
    "linkedin",
    "chatgpt",
    "openai",
    "domain",
    "hosting",
    "telstra",
    "optus",
    "vodafone",
    "energy",
    "ato",
    "insurance",
]

def clean_filename(s: str) -> str:
    """Sanitize string for filesystem path."""
    return re.sub(r'[\\/*?:"<>|]', "_", s).strip()[:100]

def decode_str(header_value: str) -> str:
    """Decode encoded email headers safely."""
    if not header_value:
        return ""
    decoded_fragments = []
    for fragment, encoding in decode_header(header_value):
        if isinstance(fragment, bytes):
            try:
                decoded_fragments.append(fragment.decode(encoding or "utf-8", errors="replace"))
            except Exception:
                decoded_fragments.append(fragment.decode("latin-1", errors="replace"))
        else:
            decoded_fragments.append(str(fragment))
    return " ".join(decoded_fragments).strip()

def search_account(email_address: str, app_password: str, output_base: Path):
    """Connect to Gmail, search for receipts, download attachments, and record metadata."""
    print(f"\n=======================================================")
    print(f" Connecting to {email_address}...")
    print(f"=======================================================")
    
    account_clean = clean_filename(email_address.split("@")[0])
    account_dir = output_base / account_clean
    account_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, app_password.replace(" ", ""))
    except Exception as e:
        print(f"[ERROR] Failed to log in to {email_address}: {e}")
        print("  -> Ensure 2-Step Verification is enabled and you used a 16-character App Password.")
        print("  -> Generate one at: https://myaccount.google.com/apppasswords")
        return []

    # Select all mail (in Gmail, '[Gmail]/All Mail' contains all inbox + archived emails)
    status, _ = mail.select('"[Gmail]/All Mail"', readonly=True)
    if status != "OK":
        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            print(f"[ERROR] Could not select mailbox for {email_address}")
            return []

    # Search for emails between dates
    # Gmail IMAP supports X-GM-RAW queries for rich searches
    date_query = f'after:2025/06/30 before:2026/07/01'
    keyword_or = " OR ".join([f'"{kw}"' if " " in kw else kw for kw in KEYWORDS])
    raw_query = f'{date_query} ({keyword_or})'
    
    print(f"Searching Gmail for receipts between 01-Jul-2025 and 30-Jun-2026...")
    status, data = mail.uid("SEARCH", None, f'X-GM-RAW "{raw_query}"')
    
    if status != "OK" or not data[0]:
        # Fallback to standard IMAP search if X-GM-RAW fails
        print("Standard IMAP search fallback...")
        status, data = mail.uid("SEARCH", None, f'(SINCE "{SINCE_DATE}" BEFORE "{BEFORE_DATE}")')
    
    if status != "OK" or not data[0]:
        print(f"No matching messages found for {email_address}.")
        mail.logout()
        return []

    uids = data[0].split()
    print(f"Found {len(uids)} potential receipt email(s). Processing...")

    results = []

    for idx, uid in enumerate(uids, start=1):
        uid_str = uid.decode()
        status, msg_data = mail.uid("FETCH", uid, "(RFC822)")
        if status != "OK" or not msg_data:
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_str(msg.get("Subject", "No Subject"))
        sender = decode_str(msg.get("From", "Unknown Sender"))
        date_str = decode_str(msg.get("Date", ""))

        # Parse date
        parsed_date = ""
        try:
            date_tuple = email.utils.parsedate_tz(date_str)
            if date_tuple:
                dt = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                parsed_date = dt.strftime("%Y-%m-%d")
        except Exception:
            parsed_date = date_str[:10]

        prefix = f"{parsed_date}_{clean_filename(sender[:25])}_{idx}"
        saved_files = []

        # Extract attachments and body
        has_attachment = False
        body_text = ""
        body_html = ""

        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            filename = part.get_filename()

            if filename:
                filename = decode_str(filename)
                ext = Path(filename).suffix.lower()
                clean_name = clean_filename(Path(filename).stem)
                save_filename = f"{prefix}_{clean_name}{ext}"
                file_path = account_dir / save_filename
                
                # Write attachment
                payload = part.get_payload(decode=True)
                if payload:
                    with open(file_path, "wb") as f:
                        f.write(payload)
                    saved_files.append(save_filename)
                    has_attachment = True
            elif content_type == "text/html":
                try:
                    body_html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    pass
            elif content_type == "text/plain":
                try:
                    body_text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    pass

        # If no attachments, save the email body as HTML/txt so receipts like Uber/Apple aren't lost
        if not has_attachment:
            if body_html:
                save_filename = f"{prefix}_receipt.html"
                file_path = account_dir / save_filename
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(body_html)
                saved_files.append(save_filename)
            elif body_text:
                save_filename = f"{prefix}_receipt.txt"
                file_path = account_dir / save_filename
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(body_text)
                saved_files.append(save_filename)

        print(f" [{idx}/{len(uids)}] {parsed_date} | {sender[:30]} | {subject[:40]} -> Saved: {len(saved_files)} file(s)")

        results.append({
            "Account": email_address,
            "Date": parsed_date,
            "Sender": sender,
            "Subject": subject,
            "Saved Files": "; ".join(saved_files),
            "Directory": str(account_dir)
        })

    mail.logout()
    return results

def main():
    print("=================================================================")
    print("       TAX RECEIPT FINDER (FY 2025-2026: 01/07/2025 - 30/06/2026)")
    print("=================================================================")
    print("This tool searches wendy.park2003@gmail.com and wendy.park1001@gmail.com")
    print("for all tax invoices, deductions, and receipts.")
    print("-----------------------------------------------------------------")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_records = []

    for acc in ACCOUNTS:
        print(f"\n--- Account: {acc} ---")
        # Check if environment variable set
        env_var_name = "GMAIL_APP_PASS_" + acc.split("@")[0].replace(".", "_").upper()
        app_pass = os.environ.get(env_var_name)

        if not app_pass:
            print(f"Please enter the 16-character Google App Password for '{acc}'.")
            print("(To generate one: Go to https://myaccount.google.com/apppasswords)")
            try:
                app_pass = getpass.getpass(f"App Password for {acc} (input will be hidden): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelled.")
                return

        if not app_pass:
            print(f"Skipping {acc} (no password provided).")
            continue

        records = search_account(acc, app_pass, OUTPUT_DIR)
        all_records.extend(records)

    # Write summary CSV
    csv_path = OUTPUT_DIR / "tax_receipts_summary_fy2025_2026.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["Account", "Date", "Sender", "Subject", "Saved Files", "Directory"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_records:
            writer.writerow(r)

    print("\n=================================================================")
    print(f" Done! Found and processed {len(all_records)} receipt items.")
    print(f" Summary CSV saved to: {csv_path}")
    print(f" Downloaded files saved in: {OUTPUT_DIR.resolve()}/")
    print("=================================================================")

if __name__ == "__main__":
    main()
