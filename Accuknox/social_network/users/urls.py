# Assuming this is in your project's urls.py or app's urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, FriendRequestViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'friend-requests', FriendRequestViewSet, basename='friend-request')
urlpatterns = router.urls
