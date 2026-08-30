#!/usr/bin/env python3
"""
Gmail Tax Receipt Finder for Current Financial Year (FY 2026-2027: 01/07/2026 - Present)
----------------------------------------------------------------------------------------
Uses existing cached OAuth tokens to search wendy.park2003@gmail.com and wendy.park1001@gmail.com.
"""

import os
import sys
import base64
import re
import csv
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

OUTPUT_DIR = Path("tax_receipts_fy2026_2027")
# Current Financial Year (starts 1 July 2026 to present)
SEARCH_QUERY = 'after:2026/06/30 (receipt OR "tax invoice" OR invoice OR "order confirmation" OR "payment received" OR subscription OR statement OR bill OR donation OR Officeworks OR Apple OR Google OR Amazon OR Uber OR ATO OR Bunnings OR "JB Hi-Fi" OR Adobe OR Microsoft OR Canva)'

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
                print(f"[ERROR] 'credentials.json' not found for {account_email}", flush=True)
                return None

            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0, prompt='consent')

        with open(token_file, "w") as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def categorize(sender, subject):
    text = f'{sender} {subject}'.lower()
    if any(k in text for k in ['belong', 'telstra', 'optus', 'vodafone', 'internet', 'mobile']):
        return 'Phone & Internet (WFH)'
    elif any(k in text for k in ['origin energy', 'energy', 'water', 'greater western water', 'power', 'electricity', 'gas']):
        return 'Home Utilities (WFH)'
    elif any(k in text for k in ['canva', 'grammarly', 'adobe', 'apple', 'microsoft', 'google', 'openai', 'chatgpt', 'zoom', 'notion', 'github', 'linkedin', 'dropbox', 'software', 'domain']):
        return 'Software & Work Subscriptions'
    elif any(k in text for k in ['uber', 'didi', 'taxi', 'flight', 'jetstar', 'qantas', 'airbnb', 'expedia', 'trip', 'agoda', 'hotel', 'ticketek']):
        return 'Work Travel & Transport'
    elif any(k in text for k in ['unisuper', 'hostplus', 'superannuation', 'insurance', 'cba', 'nab', 'commonwealth bank', 'netbank']):
        return 'Superannuation & Banking'
    elif any(k in text for k in ['unimelb', 'university', 'student', 'tuition', 'training', 'course', 'workshop', 'ielts', 'vce']):
        return 'Self-Education & Training'
    elif any(k in text for k in ['donation', 'charity', 'red cross', 'cancer council', 'gofundme']):
        return 'Donations ($2+ DGR)'
    elif any(k in text for k in ['officeworks', 'jb hi-fi', 'bunnings', 'amazon', 'kogan', 'hardware']):
        return 'Tech & Office Equipment'
    elif any(k in text for k in ['invoice', 'receipt', 'order confirmation', 'sinjeon', 'parkbongsook', 'ifly', 'plus coffee']):
        return 'Invoices & General Receipts'
    else:
        return 'Other / Review'

def process_account(account_email: str):
    print(f"\n=======================================================", flush=True)
    print(f" Connecting to {account_email} for Current FY (2026-2027)...", flush=True)
    print(f"=======================================================", flush=True)
    service = get_gmail_service(account_email)
    if not service:
        return []

    account_clean = clean_filename(account_email.split("@")[0])
    account_dir = OUTPUT_DIR / account_clean
    account_dir.mkdir(parents=True, exist_ok=True)

    print(f"Searching for receipts after 30 June 2026...", flush=True)
    
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

    print(f"Found {len(messages)} matching emails for current financial year.", flush=True)
    if not messages:
        return []

    records = []
    for idx, msg_meta in enumerate(messages, start=1):
        msg_id = msg_meta['id']
        try:
            msg = service.users().messages().get(userId='me', id=msg_id).execute()
        except Exception as e:
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
                except Exception:
                    pass

        if not saved_files:
            snippet = msg.get('snippet', '')
            save_filename = f"{prefix}_receipt.txt"
            file_path = account_dir / save_filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Account: {account_email}\nFrom: {sender}\nSubject: {subject}\nDate: {date_str}\n\nSnippet:\n{snippet}\n")
            saved_files.append(save_filename)

        category = categorize(sender, subject)
        print(f" [{idx}/{len(messages)}] [{category}] {parsed_date} | {sender[:25]} | {subject[:35]} -> Saved: {len(saved_files)} file(s)", flush=True)
        records.append({
            "Tax Category": category,
            "Date": parsed_date,
            "Account": account_email,
            "Sender": sender,
            "Subject": subject,
            "Saved Files": "; ".join(saved_files),
            "Directory": str(account_dir)
        })

    return records

def main():
    print("=================================================================", flush=True)
    print("   TAX RECEIPT FINDER (CURRENT FY 2026-2027: 01/07/2026 - PRESENT)")
    print("=================================================================", flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_records = []

    for acc in ACCOUNTS:
        records = process_account(acc)
        all_records.extend(records)

    if all_records:
        csv_path = OUTPUT_DIR / "tax_deductions_categorized_fy2026_2027.csv"
        all_records.sort(key=lambda x: (x['Tax Category'], x['Date']), reverse=True)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            fieldnames = ["Tax Category", "Date", "Account", "Sender", "Subject", "Saved Files", "Directory"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_records:
                writer.writerow(r)
        print("\n" + "="*70, flush=True)
        print(f" SUCCESS! Downloaded and indexed {len(all_records)} receipts for FY 2026-2027.", flush=True)
        print(f" Categorized CSV: {csv_path.resolve()}", flush=True)
        print(f" Saved in: {OUTPUT_DIR.resolve()}/", flush=True)
        print("="*70, flush=True)
    else:
        print("\nNo records found for FY 2026-2027.", flush=True)

if __name__ == "__main__":
    main()
