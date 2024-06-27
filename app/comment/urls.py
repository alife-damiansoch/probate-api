from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.urlpatterns import format_suffix_patterns
from comment.views import CommentListViewSet

router = DefaultRouter()
app_name = 'comment'
router.register(r'applications/comments', CommentListViewSet, basename='comment')
urlpatterns = [
    path('', include(router.urls)),
    # your specific endpoint

]
