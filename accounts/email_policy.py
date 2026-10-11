"""Quy tac email duoc phep dang ky / moi vao nhom: dung domain truong/khoa, hoac nam trong
danh sach ngoai le (ALLOWED_SIGNUP_EXTRA_EMAILS - vd email ca nhan de test gui mail khi demo).

Danh sach ngoai le chi doc tu bien moi truong, KHONG ghi cung email ca nhan vao code.
"""
from django.conf import settings


def allowed_domains():
    return [d.lower() for d in getattr(settings, "ALLOWED_SIGNUP_EMAIL_DOMAINS", [])]


def allowed_domains_text():
    return ", ".join(f"@{d}" for d in allowed_domains())


def is_allowed_email(email: str) -> bool:
    email = (email or "").strip().lower()
    if email in {e.strip().lower() for e in getattr(settings, "ALLOWED_SIGNUP_EXTRA_EMAILS", [])}:
        return True
    domains = allowed_domains()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    return not domains or domain in domains
