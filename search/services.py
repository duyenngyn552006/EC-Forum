from .models import SearchHistory

MAX_HISTORY_PER_USER = 10


def record_search(user, raw_query):
    """Luu tu khoa vao lich su tim kiem cua user - chuan hoa (strip) va xoa ban ghi
    trung lap khong phan biet hoa/thuong truoc khi tao moi, de query vua tim lai duoc
    day len dau danh sach thay vi nam im o vi tri cu. Chi giu toi da MAX_HISTORY_PER_USER
    ban ghi gan nhat lam nguon goi y tim kiem (CLAUDE.md: "luu lich su tim kiem gan day")."""
    normalized = (raw_query or "").strip()
    if not normalized or not user.is_authenticated:
        return

    SearchHistory.objects.filter(user=user, query__iexact=normalized).delete()
    SearchHistory.objects.create(user=user, query=normalized)

    stale_ids = list(
        SearchHistory.objects.filter(user=user)
        .order_by("-created_at")
        .values_list("id", flat=True)[MAX_HISTORY_PER_USER:]
    )
    if stale_ids:
        SearchHistory.objects.filter(id__in=stale_ids).delete()
