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
    path("<slug:slug>/edit/", views.group_edit, name="edit"),
    path("<slug:slug>/disable/", views.group_disable, name="disable"),
    path("<slug:slug>/enable/", views.group_enable, name="enable"),
    path("<slug:slug>/leave/", views.group_leave, name="leave"),
    path("<slug:slug>/transfer-leadership/", views.group_transfer_leadership, name="transfer_leadership"),
    path("<slug:slug>/members/add/", views.group_member_add, name="member_add"),
    path("<slug:slug>/members/bulk-invite/", views.group_member_bulk_invite, name="member_bulk_invite"),
    path("<slug:slug>/members/<int:user_id>/remove/", views.group_member_remove, name="member_remove"),
    path("<slug:slug>/members/<int:user_id>/role/", views.group_member_role, name="member_role"),
    path("<slug:slug>/join/", views.group_join_request_create, name="join_request_create"),
    path("<slug:slug>/join-requests/<int:request_id>/approve/", views.group_join_request_approve, name="join_request_approve"),
    path("<slug:slug>/join-requests/<int:request_id>/reject/", views.group_join_request_reject, name="join_request_reject"),
    path("<slug:slug>/posts/new/", views.group_post_create, name="post_create"),
    path("<slug:slug>/posts/<int:pk>/", views.GroupPostDetailView.as_view(), name="post_detail"),
    path("<slug:slug>/posts/<int:pk>/edit/", views.group_post_edit, name="post_edit"),
    path("<slug:slug>/posts/<int:pk>/delete/", views.group_post_delete, name="post_delete"),
    path("<slug:slug>/posts/<int:pk>/approve/", views.group_post_approve, name="post_approve"),
    path("<slug:slug>/posts/<int:pk>/reject/", views.group_post_reject, name="post_reject"),
]
