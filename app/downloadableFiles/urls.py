from django.urls import path
from .views import list_files, add_file, delete_file, download_file

app_name = 'downloadableFiles'

urlpatterns = [
    path('list/', list_files, name='list_files'),
    path('add/', add_file, name='add_file'),
    path('delete/<str:filename>/', delete_file, name='delete_file'),
    path('download/<str:filename>/', download_file, name='download_file'),  # Added download endpoint
]
