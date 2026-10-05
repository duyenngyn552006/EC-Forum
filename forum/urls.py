from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.PostListView.as_view(), name="post_list"),
    path("c/<slug:category_slug>/", views.PostListView.as_view(), name="post_list_by_category"),
    path("new/", views.PostCreateView.as_view(), name="post_create"),
    path("<int:pk>/", views.PostDetailView.as_view(), name="post_detail"),
    path("<int:pk>/edit/", views.PostUpdateView.as_view(), name="post_edit"),
    path("<int:pk>/delete/", views.PostDeleteView.as_view(), name="post_delete"),
    path("<int:pk>/pin/", views.pin_post, name="post_pin"),
    path("<int:pk>/unpin/", views.unpin_post, name="post_unpin"),
]
