from django.urls import path

from . import views

app_name = "hsr"

urlpatterns = [
    path("", views.index, name="index"),
    path("import/api/", views.import_api_view, name="import-api"),
    path("items/search/", views.search_item, name="item-search"),
    path("items/detail/<str:item_id>/", views.detail_item, name="item-detail"),
]
