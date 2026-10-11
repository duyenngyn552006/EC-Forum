from django.conf import settings
from django.db import models


class SearchHistory(models.Model):
    """Lich su tim kiem gan day cua user dang nhap - khong luu cho khach an danh.
    Moi query chi giu 1 ban ghi/user (xem search/services.py record_search), gioi han
    MAX_HISTORY_PER_USER ban ghi gan nhat de lam nguon goi y tim kiem."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="search_history")
    query = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Search histories"

    def __str__(self):
        return f'"{self.query}" - {self.user}'
