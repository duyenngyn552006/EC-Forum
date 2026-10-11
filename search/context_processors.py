def recent_search_bar(request):
    """Du lieu cho o goi y tim kiem o thanh tim kiem header - hien o moi trang,
    giong cach notifications.context_processors.notification_bell lam voi chuong thong bao."""
    if not request.user.is_authenticated:
        return {}

    return {
        "header_recent_searches": list(request.user.search_history.values_list("query", flat=True)[:8]),
    }
