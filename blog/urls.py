from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.PostListView.as_view(), name="list"),
    path("category/<slug:category_slug>/", views.PostListView.as_view(), name="category"),
    path("tag/<slug:tag_slug>/", views.PostListView.as_view(), name="tag"),
    path("editor/upload-image/", views.EditorImageUploadView.as_view(), name="editor_upload"),
    path("<slug:slug>/", views.PostDetailView.as_view(), name="detail"),
    path("<slug:slug>/like/", views.LikeToggleView.as_view(), name="like"),
]
