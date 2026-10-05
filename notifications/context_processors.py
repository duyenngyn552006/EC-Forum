from .models import Notification


def notification_bell(request):
    """Du lieu cho chuong thong bao kieu Facebook o header - hien o moi trang."""
    if not request.user.is_authenticated:
        return {}

    recent_notifications = list(
        request.user.notifications.select_related("actor").order_by("-created_at")[:10]
    )
    unread_count = request.user.notifications.filter(is_read=False).count()

    return {
        "bell_notifications": recent_notifications,
        "bell_unread_count": unread_count,
    }
