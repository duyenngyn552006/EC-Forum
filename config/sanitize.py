"""Loc HTML tra ve tu CKEditor 5 truoc khi luu DB.

Khong tin tuong hoan toan gioi han cua editor phia client - ai do van co the gui
thang HTML doc hai qua request POST (bo qua giao dien). Dung bleach de chi cho
phep mot danh sach the/attribute an toan, loai bo <script>, on-* event handler...
"""
import bleach

ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "h2", "h3", "h4",
    "ul", "ol", "li",
    "blockquote", "a", "img",
    "figure", "figcaption",
    "span",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    # data-mention: CKEditor Mention feature - danh dau nguoi duoc @gan the (xem groups/mentions.py)
    "span": ["class", "data-mention"],
    "figure": ["class"],
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
