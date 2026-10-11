from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("me/", views.my_profile, name="my_profile"),
    path("u/<str:username>/", views.ProfileDetailView.as_view(), name="profile_detail"),
    path("me/edit/", views.ProfileUpdateView.as_view(), name="profile_edit"),
    path("manage/users/", views.UserListView.as_view(), name="user_list"),
    path("manage/users/<int:pk>/assign-role/", views.assign_role, name="assign_role"),
    path("manage/users/<int:pk>/toggle-lock/", views.toggle_lock_account, name="toggle_lock_account"),
]
