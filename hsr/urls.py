from django.urls import path

from . import views

app_name = "hsr"

urlpatterns = [
    path("", views.index, name="index"),
    path("import/api/", views.import_api_view, name="import-api"),
    path("import/file/", views.import_file, name="import-file"),
    path("items/search/", views.search_item, name="item-search"),
    path("items/detail/<str:item_id>/", views.detail_item, name="item-detail"),
    path("items/", views.overview_item, name="item-overview"),
    path("banner/overview/<str:gacha_type>/", views.overview_banner, name="banner-overview"),
    path("banner/detail/<str:banner_id>/", views.detail_banner, name="banner-detail"),
    path("items/add/", views.add_item, name="item-add"),
    path("items/add/search/", views.add_search_item, name="item-add-search"),
    path("banner/edit/<pk>", views.EditBanner.as_view(), name="banner-edit"),
    path("pets/overview/<str:type_id>/", views.overview_pet, name="pet-overview"),
]
