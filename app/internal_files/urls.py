from django.urls import path
from . import views

urlpatterns = [
    # List all internal files or filter by application_id via query param
    path('', views.InternalFileListView.as_view(), name='internal-file-list'),

    # Create internal file for specific application
    path('application/<int:application_id>/', views.InternalFileCreateView.as_view(), name='internal-file-create'),

    # Individual file operations
    path('<int:pk>/', views.InternalFileDetailView.as_view(), name='internal-file-detail'),
    path('<int:pk>/download/', views.InternalFileDownloadView.as_view(), name='internal-file-download'),

    # PEP Check endpoint
    path('pep-check/application/<int:application_id>/', views.PEPCheckCreateView.as_view(), name='pep-check-create'),
]
