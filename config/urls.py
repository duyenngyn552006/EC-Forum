from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("captcha/", include("captcha.urls")),
    path("ckeditor5/", include("django_ckeditor_5.urls")),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
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
