from django.urls import path

from . import views

app_name = "interactions"

urlpatterns = [
    path("<str:model_key>/<int:object_id>/comment/", views.add_comment, name="add_comment"),
    path("comment/<int:pk>/edit/", views.edit_comment, name="edit_comment"),
    path("comment/<int:pk>/delete/", views.delete_comment, name="delete_comment"),
    path("<str:model_key>/<int:object_id>/like/", views.toggle_like, name="toggle_like"),
    path("<str:model_key>/<int:object_id>/save/", views.toggle_save, name="toggle_save"),
]
