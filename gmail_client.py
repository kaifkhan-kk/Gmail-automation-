import imaplib
import email
from email.header import decode_header
import streamlit as st

def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def fetch_unread_emails(log_fn=print):
    user_email = get_secret("GMAIL_USER_EMAIL")
    app_password = get_secret("GMAIL_APP_PASSWORD")
    max_emails = int(get_secret("GMAIL_MAX_EMAILS", "10"))

    if not user_email or not app_password:
        raise ValueError("GMAIL_USER_EMAIL या GMAIL_APP_PASSWORD सीक्रेट्स में मौजूद नहीं है!")

    log_fn("Gmail से कनेक्ट किया जा रहा है...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(user_email, app_password)
    mail.select("inbox")

    log_fn("अनरीड (Unread) ईमेल्स ढूँढे जा रहे हैं...")
    status, messages = mail.search(None, 'UNSEEN')
    if status != 'OK':
        log_fn("कोई ईमेल नहीं मिला।")
        return []

    email_ids = messages[0].split()
    if not email_ids:
        log_fn("कोई नया अनरीड मैसेज नहीं है।")
        return []

    log_fn(f"कुल {len(email_ids)} नए ईमेल मिले।")
    fetched_emails = []

    # जितने मैक्स ईमेल सेट हैं सिर्फ उतने ही फेच करें
    for e_id in email_ids[-max_emails:]:
        res, msg_data = mail.fetch(e_id, '(RFC822)')
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Subject extract
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                
                # Body extract
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                fetched_emails.append({
                    "subject": subject,
                    "body": body,
                    "date": msg.get("Date", ""),
                    "from": msg.get("From", "")
                })

    mail.logout()
    return fetched_emails
  
