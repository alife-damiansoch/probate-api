"""
Urls mapping for a User api
"""

from django.urls import path
from user import views
from user.views import MyTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

app_name = 'user'

urlpatterns = [
    path('create/', views.CreateUserView.as_view(), name='create'),
    path('activate/', views.ActivateUserView.as_view(), name='activate-user'),
    path('token/', MyTokenObtainPairView.as_view(), name='token'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.ManageUserView.as_view(), name='me'),
    path('', views.UserList.as_view(), name='list'),
    path('solicitors/', views.UserListNonStaff.as_view(), name='non-staff-users'),
    path('<int:pk>/', views.RetrieveUserView.as_view(), name='retrieve-user'),
    path('update_password/', views.UpdatePasswordView.as_view(), name='update_password'),  # new password update URL
    # Add the forgot password and reset password URLs
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/<uidb64>/<token>/', views.ResetPasswordView.as_view(), name='reset-password'),
    # Add Check Credentials URL
    path('check-credentials/', views.CheckCredentialsView.as_view(), name='check-credentials'),

]
