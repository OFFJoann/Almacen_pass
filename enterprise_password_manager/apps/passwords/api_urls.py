from django.urls import path
from rest_framework import routers
from . import api_views

router = routers.DefaultRouter()
router.register(r'entries', api_views.PasswordEntryViewSet, basename='entry')
router.register(r'folders', api_views.FolderViewSet, basename='folder')
router.register(r'categories', api_views.CategoryViewSet, basename='category')
router.register(r'tags', api_views.TagViewSet, basename='tag')

urlpatterns = [
    path('generate/', api_views.api_generate_password, name='api_generate'),
] + router.urls
