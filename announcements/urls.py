from django.urls import path

from . import views

app_name = "announcements"

urlpatterns = [
    path("", views.AnnouncementListView.as_view(), name="list"),
    path("new/", views.announcement_create, name="create"),
    path("<int:pk>/", views.AnnouncementDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.announcement_edit, name="edit"),
    path("<int:pk>/pin/", views.announcement_pin, name="pin"),
    path("<int:pk>/unpin/", views.announcement_unpin, name="unpin"),
]
