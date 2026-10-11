from django.urls import path

from . import views

app_name = "interactions"

urlpatterns = [
    path("<str:model_key>/<int:object_id>/comment/", views.add_comment, name="add_comment"),
    path("comment/<int:pk>/edit/", views.edit_comment, name="edit_comment"),
    path("comment/<int:pk>/delete/", views.delete_comment, name="delete_comment"),
    path("<str:model_key>/<int:object_id>/like/", views.toggle_like, name="toggle_like"),
    path("<str:model_key>/<int:object_id>/save/", views.toggle_save, name="toggle_save"),
    path("<str:model_key>/<int:object_id>/poll/new/", views.poll_create, name="poll_create"),
    path("poll/<int:poll_id>/vote/", views.poll_vote, name="poll_vote"),
    path("poll/<int:poll_id>/delete/", views.poll_delete, name="poll_delete"),
    path("<str:model_key>/<int:object_id>/follow/", views.toggle_follow, name="toggle_follow"),
    path("following/", views.following_list, name="following"),
    path("document/<int:pk>/download/", views.download_document, name="download_document"),
]
