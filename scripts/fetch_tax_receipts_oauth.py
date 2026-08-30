#!/usr/bin/env python3
"""
Gmail Tax Receipt Finder using Google OAuth 2.0 (Official Gmail API)
--------------------------------------------------------------------
Searches wendy.park2003@gmail.com and wendy.park1001@gmail.com for all tax receipts,
invoices, and bills for FY 2025-2026 (01/07/2025 - 30/06/2026), downloads all PDF/image
attachments, and creates a summary CSV for your tax return.
"""

import os
import sys
import base64
import re
import csv
import subprocess
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
ACCOUNTS = [
    "wendy.park2003@gmail.com",
    "wendy.park1001@gmail.com",
]

OUTPUT_DIR = Path("tax_receipts_fy2025_2026")
SEARCH_QUERY = 'after:2025/06/30 before:2026/07/01 (receipt OR "tax invoice" OR invoice OR "order confirmation" OR "payment received" OR subscription OR statement OR bill OR donation OR Officeworks OR Apple OR Google OR Amazon OR Uber OR ATO OR Bunnings OR "JB Hi-Fi" OR Adobe OR Microsoft OR Canva)'

def clean_filename(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", s).strip()[:100]

def get_gmail_service(account_email: str):
    token_file = f"token_{clean_filename(account_email.split('@')[0])}.json"
    creds = None
    
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        
        if not creds:
            if not os.path.exists("credentials.json"):
                print("\n[ERROR] 'credentials.json' not found in this folder.", flush=True)
                return None

            print(f"\n" + "="*65, flush=True)
            print(f" Starting sign-in for: {account_email}", flush=True)
            print(f" Please log in as: {account_email} in the browser window.", flush=True)
            print("="*65 + "\n", flush=True)
            
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0, prompt='consent')

        with open(token_file, "w") as token:
            token.write(creds.to_json())
        print(f"Authentication successful for {account_email}!\n", flush=True)

    return build('gmail', 'v1', credentials=creds)

def process_account(account_email: str):
    print(f"\n=======================================================", flush=True)
    print(f" Connecting to {account_email} via Gmail API...", flush=True)
    print(f"=======================================================", flush=True)
    service = get_gmail_service(account_email)
    if not service:
        return []

    account_clean = clean_filename(account_email.split("@")[0])
    account_dir = OUTPUT_DIR / account_clean
    account_dir.mkdir(parents=True, exist_ok=True)

    print(f"Searching for FY 2025-2026 receipts in {account_email}...", flush=True)
    
    messages = []
    page_token = None
    while True:
        resp = service.users().messages().list(
            userId='me',
            q=SEARCH_QUERY,
            pageToken=page_token
        ).execute()
        msgs = resp.get('messages', [])
        messages.extend(msgs)
        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    print(f"Found {len(messages)} matching receipts/invoices.", flush=True)
    if not messages:
        return []

    records = []
    for idx, msg_meta in enumerate(messages, start=1):
        msg_id = msg_meta['id']
        try:
            msg = service.users().messages().get(userId='me', id=msg_id).execute()
        except Exception as e:
            print(f"  [Warning] Could not fetch message {msg_id}: {e}", flush=True)
            continue

        payload = msg.get('payload', {})
        headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
        
        subject = headers.get('subject', 'No Subject')
        sender = headers.get('from', 'Unknown Sender')
        date_str = headers.get('date', '')

        parsed_date = ""
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            parsed_date = dt.strftime("%Y-%m-%d")
        except Exception:
            parsed_date = date_str[:10]

        prefix = f"{parsed_date}_{clean_filename(sender[:25])}_{idx}"
        saved_files = []

        # Find attachments recursively
        parts = [payload]
        while parts:
            part = parts.pop(0)
            if 'parts' in part:
                parts.extend(part['parts'])
            filename = part.get('filename')
            body = part.get('body', {})
            att_id = body.get('attachmentId')
            
            if filename and att_id:
                try:
                    attachment = service.users().messages().attachments().get(
                        userId='me', messageId=msg_id, id=att_id
                    ).execute()
                    data = base64.urlsafe_b64decode(attachment.get('data', ''))
                    ext = Path(filename).suffix
                    clean_name = clean_filename(Path(filename).stem)
                    save_filename = f"{prefix}_{clean_name}{ext}"
                    file_path = account_dir / save_filename
                    with open(file_path, "wb") as f:
                        f.write(data)
                    saved_files.append(save_filename)
                except Exception as err:
                    print(f"    Failed to download attachment {filename}: {err}", flush=True)

        # If no attachments, save snippet/body
        if not saved_files:
            snippet = msg.get('snippet', '')
            save_filename = f"{prefix}_receipt.txt"
            file_path = account_dir / save_filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Account: {account_email}\nFrom: {sender}\nSubject: {subject}\nDate: {date_str}\n\nSnippet:\n{snippet}\n")
            saved_files.append(save_filename)

        print(f" [{idx}/{len(messages)}] {parsed_date} | {sender[:30]} | {subject[:40]} -> Saved: {len(saved_files)} file(s)", flush=True)
        records.append({
            "Account": account_email,
            "Date": parsed_date,
            "Sender": sender,
            "Subject": subject,
            "Saved Files": "; ".join(saved_files),
            "Directory": str(account_dir)
        })

    return records

def main():
    print("=================================================================", flush=True)
    print("      GOOGLE OAUTH GMAIL TAX RECEIPT FINDER (FY 2025-2026)", flush=True)
    print("=================================================================", flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_records = []

    for acc in ACCOUNTS:
        records = process_account(acc)
        all_records.extend(records)

    if all_records:
        csv_path = OUTPUT_DIR / "tax_receipts_summary_fy2025_2026.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            fieldnames = ["Account", "Date", "Sender", "Subject", "Saved Files", "Directory"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_records:
                writer.writerow(r)
        print("\n" + "="*70, flush=True)
        print(f" SUCCESS! Downloaded and indexed {len(all_records)} tax receipts.", flush=True)
        print(f" Summary CSV: {csv_path.resolve()}", flush=True)
        print(f" Files saved in: {OUTPUT_DIR.resolve()}/", flush=True)
        print("="*70, flush=True)
    else:
        print("\nNo records processed.", flush=True)

if __name__ == "__main__":
    main()
