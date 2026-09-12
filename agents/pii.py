"""Redact common contact details before resume text is sent to an LLM."""
import re


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
SG_PHONE_RE = re.compile(r"(?<!\d)(?:\+?65[\s-]?)?[689]\d{3}[\s-]?\d{4}(?!\d)")


def redact_contact_pii(text):
    """Replace email addresses and Singapore phone numbers with safe labels."""
    if not isinstance(text, str):
        raise TypeError("PII redaction input must be text.")
    text = EMAIL_RE.sub("[EMAIL]", text)
    return SG_PHONE_RE.sub("[PHONE]", text)
