"""
=============================================================
  ai_parser.py — Gemini-powered email parser
=============================================================
Sends each raw email (Subject + Body) to Gemini and asks it
to extract structured contact / enquiry fields.

Returned fields per email:
    name    – Full name of the sender (best guess)
    email   – Email address
    phone   – Phone number (or "N/A")
    query   – Summary of the enquiry / request
"""

import json
import re
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Configure the Gemini client once at import time
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

_MODEL_NAME = "gemini-1.5-flash"  # fast & cost-effective

_SYSTEM_PROMPT = """
You are a data-extraction assistant. Given a raw email (sender info, subject, body),
extract exactly four fields and return them as a JSON object.

Fields:
  name   – Full name of the person who sent the email.
             If not clearly stated, use the sender name provided.
  email  – Email address of the sender.
  phone  – Phone number mentioned in the email, or "N/A" if absent.
  query  – A concise one-to-three sentence summary of what the sender wants or is asking.

Rules:
  - Return ONLY valid JSON, no markdown fences, no extra text.
  - All values must be strings.
  - Do not invent information not present in the input.

Example output:
{"name": "Alice Smith", "email": "alice@example.com", "phone": "+1-555-0100", "query": "Requesting a quote for web design services."}
""".strip()


def _build_user_message(email_dict: dict) -> str:
    return (
        f"Sender name: {email_dict.get('sender_name', '')}\n"
        f"Sender email: {email_dict.get('sender_email', '')}\n"
        f"Date: {email_dict.get('date', '')}\n"
        f"Subject: {email_dict.get('subject', '')}\n\n"
        f"Body:\n{email_dict.get('body', '')[:3000]}"
    )


def _safe_json_parse(text: str) -> dict | None:
    """Attempt to extract the first JSON object from a Gemini response."""
    text = text.strip()
    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try finding the first {...} block
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def parse_email(email_dict: dict, log_fn=None) -> dict:
    """
    Parse a single email dict with Gemini.

    Args:
        email_dict: Dict with keys sender_name, sender_email, date, subject, body.
        log_fn:     Optional callable(message: str) for progress logging.

    Returns:
        Dict with keys: name, email, phone, query, raw_subject, raw_date.
        Falls back to raw values if Gemini parsing fails.
    """
    def _log(msg: str):
        logger.info(msg)
        if log_fn:
            log_fn(msg)

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in Replit Secrets.")

    subject = email_dict.get("subject", "(no subject)")
    _log(f'🤖 Parsing: "{subject[:60]}"…')

    model = genai.GenerativeModel(
        model_name=_MODEL_NAME,
        system_instruction=_SYSTEM_PROMPT,
    )

    user_message = _build_user_message(email_dict)

    try:
        response = model.generate_content(user_message)
        raw_output = response.text or ""
        parsed = _safe_json_parse(raw_output)

        if parsed and all(k in parsed for k in ("name", "email", "phone", "query")):
            parsed["raw_subject"] = subject
            parsed["raw_date"] = email_dict.get("date", "")
            return parsed
        else:
            _log("⚠️  Gemini returned unexpected format; using fallback for this email.")

    except Exception as exc:
        _log(f'⚠️  Gemini error for "{subject[:40]}": {exc}')

    # Fallback: use raw email fields
    return {
        "name": email_dict.get("sender_name", ""),
        "email": email_dict.get("sender_email", ""),
        "phone": "N/A",
        "query": subject,
        "raw_subject": subject,
        "raw_date": email_dict.get("date", ""),
    }


def parse_emails(emails: list[dict], log_fn=None) -> list[dict]:
    """Parse a list of email dicts. Returns list of parsed result dicts."""
    results = []
    for i, em in enumerate(emails, 1):
        if log_fn:
            log_fn(f"📧 Processing email {i}/{len(emails)}…")
        results.append(parse_email(em, log_fn=log_fn))
    return results
