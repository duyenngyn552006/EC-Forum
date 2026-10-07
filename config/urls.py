from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Vo hieu hoa tinh nang "Doi Email" cua allauth - email dang nhap gan voi MSSV va
    # bi gioi han domain @due.udn.vn luc dang ky (xem accounts/forms.py), nhung form
    # doi email mac dinh cua allauth KHONG di qua validate domain do, se cho phep them
    # email domain bat ky neu khong chan. Dat TRUOC include("allauth.urls") de ghi de.
    path("accounts/email/", RedirectView.as_view(pattern_name="home"), name="account_email"),
    path("accounts/", include("allauth.urls")),
    path("captcha/", include("captcha.urls")),
    path("ckeditor5/", include("django_ckeditor_5.urls")),
    path("", views.home_view, name="home"),
    path("profile/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("announcements/", include(("announcements.urls", "announcements"), namespace="announcements")),
    path("forum/", include(("forum.urls", "forum"), namespace="forum")),
    path("groups/", include(("groups.urls", "groups"), namespace="groups")),
    path("interact/", include(("interactions.urls", "interactions"), namespace="interactions")),
    path("notifications/", include(("notifications.urls", "notifications"), namespace="notifications")),
    path("moderation/", include(("moderation.urls", "moderation"), namespace="moderation")),
    path("dashboard/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),
    path("search/", include(("search.urls", "search"), namespace="search")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
