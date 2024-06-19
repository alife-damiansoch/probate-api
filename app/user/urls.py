"""
Urls mapping for a User api
"""

from django.urls import path
from user import views

app_name = 'user'

urlpatterns = [
    path('create/', views.CreateUserView.as_view(), name='create'),
    path("token/", views.CreateTokenView.as_view(), name='token'),
    path('me/', views.ManageUserView.as_view(), name='me'),
    path('', views.UserList.as_view(), name='list'),
    path('solicitors/', views.UserListNonStaff.as_view(), name='non-staff-users'),
    path('<int:pk>/', views.RetrieveUserView.as_view(), name='retrieve-user'),
]
