from django.urls import path

from . import views

app_name = "search"

urlpatterns = [
    path("", views.search_view, name="results"),
    path("suggest/", views.suggest_view, name="suggest"),
    path("history/clear/", views.clear_search_history, name="clear_history"),
]
