#!/usr/bin/env python3
"""
Tax Receipt Extractor for Google Takeout (.mbox files)
------------------------------------------------------
Extracts tax invoices, receipts, and purchase confirmations from downloaded Google Takeout .mbox files.
"""

import os
import sys
import mailbox
import email
from email.header import decode_header
import re
import csv
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("tax_receipts_fy2025_2026")
KEYWORDS = [
    "receipt", "tax invoice", "invoice", "order confirmation", "payment confirmation",
    "payment received", "subscription", "statement", "bill", "donation", "officeworks",
    "apple", "google", "amazon", "uber", "bunnings", "jbhifi", "adobe", "microsoft",
    "zoom", "notion", "canva", "github", "linkedin", "chatgpt", "openai", "domain",
    "hosting", "telstra", "optus", "vodafone", "energy", "ato", "insurance"
]

def clean_filename(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", s).strip()[:100]

def decode_str(header_value: str) -> str:
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

def process_mbox(mbox_path: Path):
    print(f"Reading MBOX file: {mbox_path.name}...")
    account_name = mbox_path.stem
    account_dir = OUTPUT_DIR / clean_filename(account_name)
    account_dir.mkdir(parents=True, exist_ok=True)

    mbox = mailbox.mbox(str(mbox_path))
    records = []
    idx = 0

    for msg in mbox:
        subject = decode_str(msg.get("Subject", "No Subject"))
        sender = decode_str(msg.get("From", "Unknown Sender"))
        date_str = decode_str(msg.get("Date", ""))

        parsed_date = ""
        dt = None
        try:
            date_tuple = email.utils.parsedate_tz(date_str)
            if date_tuple:
                dt = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                parsed_date = dt.strftime("%Y-%m-%d")
        except Exception:
            parsed_date = date_str[:10]

        # Check date range (FY 2025-2026: 2025-07-01 to 2026-06-30)
        if dt:
            fy_start = datetime(2025, 7, 1)
            fy_end = datetime(2026, 6, 30, 23, 59, 59)
            if dt < fy_start or dt > fy_end:
                continue

        # Check keywords
        full_text = f"{subject.lower()} {sender.lower()}"
        if not any(kw in full_text for kw in KEYWORDS):
            continue

        idx += 1
        prefix = f"{parsed_date}_{clean_filename(sender[:25])}_{idx}"
        saved_files = []
        has_attachment = False

        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                filename = decode_str(filename)
                ext = Path(filename).suffix.lower()
                clean_name = clean_filename(Path(filename).stem)
                save_filename = f"{prefix}_{clean_name}{ext}"
                file_path = account_dir / save_filename
                payload = part.get_payload(decode=True)
                if payload:
                    with open(file_path, "wb") as f:
                        f.write(payload)
                    saved_files.append(save_filename)
                    has_attachment = True

        if not has_attachment:
            body = msg.get_payload(decode=True)
            if body:
                save_filename = f"{prefix}_receipt.html"
                file_path = account_dir / save_filename
                with open(file_path, "wb") as f:
                    f.write(body)
                saved_files.append(save_filename)

        print(f" [{idx}] {parsed_date} | {sender[:30]} | {subject[:40]} -> Saved: {len(saved_files)} file(s)")
        records.append({
            "Account": account_name,
            "Date": parsed_date,
            "Sender": sender,
            "Subject": subject,
            "Saved Files": "; ".join(saved_files),
            "Directory": str(account_dir)
        })

    return records

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mbox_files = list(Path(".").glob("*.mbox"))
    if not mbox_files:
        print("No .mbox files found in the current directory.")
        print("Download your emails from https://takeout.google.com and drop the .mbox file here.")
        return

    all_records = []
    for f in mbox_files:
        records = process_mbox(f)
        all_records.extend(records)

    csv_path = OUTPUT_DIR / "tax_receipts_summary_fy2025_2026.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["Account", "Date", "Sender", "Subject", "Saved Files", "Directory"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_records:
            writer.writerow(r)
    print(f"\nDone! Extracted {len(all_records)} receipts to {OUTPUT_DIR}/ and summary to {csv_path}")

if __name__ == "__main__":
    main()
