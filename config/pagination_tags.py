"""Template tag phan trang dung chung (dang ky lam builtin trong settings.TEMPLATES, khong can {% load %}).

- {% page_url n %}       -> "?<cac tham so GET hien tai, tru page>&page=n" (giu nguyen bo loc/sap xep khi chuyen trang)
- {% page_window page_obj as pages %} -> [1, None, 4, 5, 6, None, 12]  (None = dau "...")
"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def page_url(context, number):
    request = context.get("request")
    params = request.GET.copy() if request is not None else {}
    if hasattr(params, "pop"):
        params.pop("page", None)
    query = params.urlencode() if hasattr(params, "urlencode") else ""
    return f"?{query}&page={number}" if query else f"?page={number}"


@register.simple_tag
def page_window(page_obj, around=2):
    """Trang dau, trang cuoi va `around` trang quanh trang hien tai; khoang cach > 1 trang thay bang None."""
    total = page_obj.paginator.num_pages
    current = page_obj.number
    wanted = {1, total} | set(range(max(1, current - around), min(total, current + around) + 1))
    pages, previous = [], 0
    for n in sorted(wanted):
        if n - previous > 1:
            pages.append(None)
        pages.append(n)
        previous = n
    return pages
