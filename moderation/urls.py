from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    path("report/<str:model_key>/<int:object_id>/", views.create_report, name="create_report"),
    path("reports/", views.report_list, name="report_list"),
    path("reports/<int:pk>/resolve/", views.report_resolve, name="report_resolve"),
    path("pending-content/", views.pending_content_list, name="pending_content_list"),
    path("pending-content/<str:model_key>/<int:object_id>/approve/", views.approve_content, name="approve_content"),
    path("pending-content/<str:model_key>/<int:object_id>/reject/", views.reject_content, name="reject_content"),
    path("appeal/new/", views.appeal_create, name="appeal_create"),
    path("appeals/", views.appeal_list, name="appeal_list"),
    path("appeals/<int:pk>/review/", views.appeal_review, name="appeal_review"),
    path("keywords/", views.SensitiveKeywordListView.as_view(), name="keyword_list"),
    path("keywords/new/", views.SensitiveKeywordCreateView.as_view(), name="keyword_create"),
    path("keywords/<int:pk>/edit/", views.SensitiveKeywordUpdateView.as_view(), name="keyword_edit"),
    path("keywords/<int:pk>/delete/", views.SensitiveKeywordDeleteView.as_view(), name="keyword_delete"),
]
