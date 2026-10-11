"""Loc HTML tra ve tu CKEditor 5 truoc khi luu DB.

Khong tin tuong hoan toan gioi han cua editor phia client - ai do van co the gui
thang HTML doc hai qua request POST (bo qua giao dien). Dung bleach de chi cho
phep mot danh sach the/attribute an toan, loai bo <script>, on-* event handler...
"""
import re

import bleach

ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "h2", "h3", "h4",
    "ul", "ol", "li",
    "blockquote", "a", "img",
    "figure", "figcaption",
    "span",
    # Khoi code CKEditor: <pre><code class="language-python">...</code></pre>
    "pre", "code",
]

_CODE_LANGUAGE_CLASS = re.compile(r"language-[a-z0-9+#-]{1,20}")


def _allow_code_attribute(tag, name, value):
    """<code> chi giu class dang "language-xxx" (CKEditor ghi ngon ngu khoi code), bo moi attribute khac."""
    return name == "class" and bool(_CODE_LANGUAGE_CLASS.fullmatch(value))


ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    # data-mention: CKEditor Mention feature - danh dau nguoi duoc @gan the (xem groups/mentions.py)
    "span": ["class", "data-mention"],
    "figure": ["class"],
    "code": _allow_code_attribute,
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def sanitize_html(raw_html: str) -> str:
    if not raw_html:
        return raw_html
    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
