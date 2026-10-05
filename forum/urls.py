from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("tags/", views.TagListView.as_view(), name="tag_list"),
    path("tags/new/", views.TagCreateView.as_view(), name="tag_create"),
    path("tags/<int:pk>/edit/", views.TagUpdateView.as_view(), name="tag_edit"),
    path("tags/<int:pk>/delete/", views.TagDeleteView.as_view(), name="tag_delete"),
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/new/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", views.CategoryDeleteView.as_view(), name="category_delete"),
    path("", views.PostListView.as_view(), name="post_list"),
    path("c/<slug:category_slug>/", views.PostListView.as_view(), name="post_list_by_category"),
    path("new/", views.PostCreateView.as_view(), name="post_create"),
    path("<int:pk>/", views.PostDetailView.as_view(), name="post_detail"),
    path("<int:pk>/edit/", views.PostUpdateView.as_view(), name="post_edit"),
    path("<int:pk>/delete/", views.PostDeleteView.as_view(), name="post_delete"),
    path("<int:pk>/pin/", views.pin_post, name="post_pin"),
    path("<int:pk>/unpin/", views.unpin_post, name="post_unpin"),
]
