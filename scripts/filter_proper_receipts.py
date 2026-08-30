#!/usr/bin/env python3
"""
Proper Tax Receipt Extractor & Cleaner
--------------------------------------
Filters out marketing emails, alerts, and newsletters.
Extracts ONLY genuine financial receipts, tax invoices, and bills
with amounts paid ($), vendor names, and dates.
"""

import os
import sys
import re
import csv
import base64
import html
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
ACCOUNTS = [
    "wendy.park2003@gmail.com",
    "wendy.park1001@gmail.com",
]

OUTPUT_DIR = Path("tax_receipts_verified")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Words indicating marketing / non-receipt emails to strictly reject
EXCLUDE_SUBJECT_PATTERNS = [
    r'we miss you', r'exclusive.*offer', r'expires soon', r'sale', r'off.*styles',
    r'new arrivals', r'save \d+%', r'discount', r'security alert', r'job.*recommendation',
    r'internship', r'appeared in \d+ search', r'just messaged you', r'sent you a message',
    r'document shared', r'share request', r'folder shared', r'declined: ', r'real-time location',
    r'are you renting', r'you missed photos', r'review your stay', r'how is your stay',
    r'the wrap:', r'under the spotlight', r'hackathon', r'challenge', r'newsletter',
    r'did you make this change', r'terms of use', r'privacy notice', r'privacy settings',
    r'delivery status notification', r'fail', r'pass', r'bonus points', r'win a share',
    r'sneak peek', r'new catalogue', r'backlog deserves', r'keynote', r'alumni news',
    r'abortion', r'prolife', r'alone australia', r'charlie kirk'
]

# Patterns that indicate a real transaction / payment / invoice
RECEIPT_INDICATORS = [
    r'tax invoice', r'tax receipt', r'your receipt', r'order confirmation', r'payment confirmation',
    r'thanks for your payment', r'payment received', r'your payment of', r'your bill',
    r'your statement', r'account statement', r'ticket order confirmation', r'booking confirmation',
    r'e-ticket', r'your order from', r'order #', r'invoice #', r'tax statement',
    r'subscription confirmed', r'membership renewal'
]

AMOUNT_REGEX = re.compile(r'(?:(?:AUD|A\$|\$|USD|US\$)\s*(\d{1,5}(?:,\d{3})*(?:\.\d{2})?)|(\d{1,5}(?:,\d{3})*\.\d{2})\s*(?:AUD|USD))', re.IGNORECASE)

def clean_filename(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", s).strip()[:100]

def is_valid_receipt(sender: str, subject: str, body_text: str, has_pdf: bool) -> tuple:
    """Check if an email is a genuine receipt and extract payment amount."""
    full_header = f"{sender} {subject}".lower()
    
    # 1. Reject obvious non-receipt subjects
    for pattern in EXCLUDE_SUBJECT_PATTERNS:
        if re.search(pattern, full_header):
            return False, ""

    # 2. Check for positive indicators
    has_indicator = False
    for ind in RECEIPT_INDICATORS:
        if re.search(ind, full_header) or re.search(ind, body_text.lower()[:500]):
            has_indicator = True
            break

    # If it has a PDF invoice attachment from a known service or has positive subject indicator
    if has_pdf:
        has_indicator = True

    # 3. Extract amount
    amount_str = ""
    matches = AMOUNT_REGEX.findall(body_text)
    if matches:
        for m in matches:
            val = m[0] or m[1]
            if val and float(val.replace(',', '')) > 0:
                amount_str = f"${val}"
                break

    # If subject says "Thanks for your payment" or "Tax Invoice", it's a valid receipt
    if has_indicator:
        return True, amount_str

    # If amount found and vendor looks like a commercial sender
    if amount_str and any(k in full_header for k in ['uber', 'belong', 'origin', 'water', 'apple', 'google', 'canva', 'grammarly', 'jetstar', 'qantas', 'airbnb', 'paypal', 'ticketek', 'chemist']):
        return True, amount_str

    return False, ""

def categorize(sender: str, subject: str) -> str:
    text = f"{sender} {subject}".lower()
    if any(k in text for k in ['belong', 'telstra', 'optus', 'vodafone', 'internet', 'mobile', 'telecom']):
        return 'Phone & Internet (WFH)'
    elif any(k in text for k in ['origin energy', 'energy', 'water', 'greater western water', 'power', 'electricity', 'gas']):
        return 'Home Utilities (WFH)'
    elif any(k in text for k in ['canva', 'grammarly', 'adobe', 'apple', 'microsoft', 'google', 'openai', 'chatgpt', 'zoom', 'notion', 'github', 'linkedin', 'dropbox']):
        return 'Software & Work Subscriptions'
    elif any(k in text for k in ['uber', 'didi', 'taxi', 'flight', 'jetstar', 'qantas', 'airbnb', 'booking', 'trip', 'agoda', 'hotel', 'ticketek']):
        return 'Work Travel & Transport'
    elif any(k in text for k in ['unisuper', 'hostplus', 'superannuation', 'ishares', 'vanguard', 'distribution', 'tax statement']):
        return 'Superannuation & Investments'
    elif any(k in text for k in ['unimelb', 'university', 'student', 'tuition', 'training', 'ielts', 'vce', 'course']):
        return 'Self-Education & Training'
    elif any(k in text for k in ['donation', 'charity', 'red cross', 'cancer council']):
        return 'Donations ($2+ DGR)'
    elif any(k in text for k in ['officeworks', 'jb hi-fi', 'bunnings', 'amazon', 'kogan', 'harvey']):
        return 'Tech & Office Equipment'
    else:
        return 'Invoices & General Expenses'

def get_body_and_attachments(service, user_id, msg_id, payload):
    """Recursively extract plain text body and attachments."""
    body_text = ""
    attachments = []
    
    parts = [payload]
    while parts:
        part = parts.pop(0)
        mime_type = part.get('mimeType', '')
        filename = part.get('filename', '')
        body = part.get('body', {})
        att_id = body.get('attachmentId')

        if filename and att_id:
            attachments.append({
                'filename': filename,
                'att_id': att_id,
                'size': body.get('size', 0)
            })

        if mime_type == 'text/plain' and 'data' in body:
            try:
                body_text += base64.urlsafe_b64decode(body['data']).decode('utf-8', errors='ignore')
            except Exception:
                pass
        elif mime_type == 'text/html' and 'data' in body and not body_text:
            try:
                raw_html = base64.urlsafe_b64decode(body['data']).decode('utf-8', errors='ignore')
                # Simple HTML to text
                text = re.sub(r'<[^>]+>', ' ', raw_html)
                body_text += html.unescape(text)
            except Exception:
                pass

        if 'parts' in part:
            parts.extend(part['parts'])

    return body_text, attachments

def process_proper_receipts(account_email: str):
    token_file = f"token_{clean_filename(account_email.split('@')[0])}.json"
    if not os.path.exists(token_file):
        print(f"Token file {token_file} missing.")
        return []

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    service = build('gmail', 'v1', credentials=creds)

    print(f"\n=======================================================")
    print(f" Scanning {account_email} for PROPER Receipts & Tax Invoices...")
    print(f"=======================================================")

    account_clean = clean_filename(account_email.split("@")[0])
    account_dir = OUTPUT_DIR / account_clean
    account_dir.mkdir(parents=True, exist_ok=True)

    # Search for both FY25-26 and FY26-27 (from 01-Jul-2025 onwards)
    query = 'after:2025/06/30 (receipt OR "tax invoice" OR invoice OR "payment received" OR "thanks for your payment" OR statement OR bill OR subscription OR Belong OR Origin OR Uber OR Apple OR Google OR Canva OR Grammarly OR iShares OR UniSuper OR "Greater Western Water")'
    
    messages = []
    page_token = None
    while True:
        resp = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
        messages.extend(resp.get('messages', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    print(f"Scanning {len(messages)} candidate emails...")
    valid_receipts = []

    for idx, m in enumerate(messages, start=1):
        msg_id = m['id']
        try:
            msg = service.users().messages().get(userId='me', id=msg_id).execute()
        except Exception:
            continue

        payload = msg.get('payload', {})
        headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
        
        subject = headers.get('subject', 'No Subject')
        sender = headers.get('from', 'Unknown Sender')
        date_str = headers.get('date', '')

        # Parse date
        parsed_date = ""
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            parsed_date = dt.strftime("%Y-%m-%d")
        except Exception:
            parsed_date = date_str[:10]

        body_text, attachments = get_body_and_attachments(service, 'me', msg_id, payload)
        has_pdf = any(att['filename'].lower().endswith('.pdf') for att in attachments)

        valid, amount = is_valid_receipt(sender, subject, body_text, has_pdf)
        if not valid:
            continue

        # Extract cleaner vendor name
        vendor = sender.split('<')[0].replace('"', '').strip()
        category = categorize(vendor, subject)

        prefix = f"{parsed_date}_{clean_filename(vendor[:20])}_{idx}"
        saved_files = []

        # Download actual PDF / image attachments
        for att in attachments:
            fname = att['filename']
            ext = Path(fname).suffix.lower()
            if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.heic']:
                try:
                    attachment = service.users().messages().attachments().get(
                        userId='me', messageId=msg_id, id=att['att_id']
                    ).execute()
                    data = base64.urlsafe_b64decode(attachment.get('data', ''))
                    save_name = f"{prefix}_{clean_filename(Path(fname).stem)}{ext}"
                    fpath = account_dir / save_name
                    with open(fpath, 'wb') as f:
                        f.write(data)
                    saved_files.append(save_name)
                except Exception:
                    pass

        # If no attachments, save a clean text receipt receipt summary
        if not saved_files:
            clean_body_snippet = re.sub(r'\s+', ' ', body_text[:600]).strip()
            save_name = f"{prefix}_receipt.txt"
            fpath = account_dir / save_name
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(f"Account: {account_email}\nDate: {parsed_date}\nVendor: {vendor}\nSubject: {subject}\nAmount: {amount}\n\nReceipt Details:\n{clean_body_snippet}\n")
            saved_files.append(save_name)

        print(f"  [✓ RECEIPT] {parsed_date} | {vendor[:20]} | {amount:<8} | {subject[:35]}")
        valid_receipts.append({
            "Financial Year": "FY 2025-2026" if parsed_date < "2026-07-01" else "FY 2026-2027",
            "Date": parsed_date,
            "Tax Category": category,
            "Vendor / Merchant": vendor,
            "Subject": subject,
            "Amount Paid": amount,
            "Account": account_email,
            "Saved File": saved_files[0] if saved_files else "",
            "Directory": str(account_dir)
        })

    return valid_receipts

def main():
    all_receipts = []
    for acc in ACCOUNTS:
        receipts = process_proper_receipts(acc)
        all_receipts.extend(receipts)

    # Sort by Date descending
    all_receipts.sort(key=lambda x: x['Date'], reverse=True)

    csv_path = OUTPUT_DIR / "VERIFIED_PROPER_TAX_RECEIPTS.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            "Financial Year", "Date", "Tax Category", "Vendor / Merchant",
            "Amount Paid", "Subject", "Saved File", "Account", "Directory"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_receipts:
            writer.writerow(r)

    print("\n" + "="*75)
    print(f" TOTAL VERIFIED PROPER RECEIPTS EXTRACTED: {len(all_receipts)}")
    print(f" Summary CSV: {csv_path.resolve()}")
    print(f" Files Folder: {OUTPUT_DIR.resolve()}/")
    print("="*75)

if __name__ == "__main__":
    main()
