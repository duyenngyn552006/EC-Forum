from django.urls import path

from . import views

app_name = "groups"

urlpatterns = [
    path("", views.GroupListView.as_view(), name="list"),
    path("new/", views.group_create, name="create"),
    path("pending/", views.pending_group_list, name="pending_list"),
    path("pending/<int:pk>/approve/", views.group_approve, name="approve"),
    path("pending/<int:pk>/reject/", views.group_reject, name="reject"),
    path("<slug:slug>/", views.GroupDetailView.as_view(), name="detail"),
    path("<slug:slug>/posts/new/", views.group_post_create, name="post_create"),
    path("<slug:slug>/posts/<int:pk>/", views.GroupPostDetailView.as_view(), name="post_detail"),
    path("<slug:slug>/posts/<int:pk>/edit/", views.group_post_edit, name="post_edit"),
    path("<slug:slug>/posts/<int:pk>/delete/", views.group_post_delete, name="post_delete"),
]
