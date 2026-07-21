from django.urls import path
from rest_framework import routers
from . import api_views

router = routers.DefaultRouter()
router.register(r'users', api_views.UserViewSet)
router.register(r'groups', api_views.GroupViewSet)

urlpatterns = router.urls
