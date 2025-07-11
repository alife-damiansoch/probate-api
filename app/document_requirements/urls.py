from django.urls import path
from . import views

app_name = 'document_requirements'

urlpatterns = [
    # Document Types
    path('api/document-types/',
         views.list_document_types,
         name='list_document_types'),

    # Application Document Requirements
    path('api/applications/<int:application_id>/document-requirements/',
         views.get_application_requirements,
         name='get_application_requirements'),

    path('api/applications/<int:application_id>/document-requirements/add/',
         views.add_document_requirement,
         name='add_document_requirement'),

    path('api/applications/<int:application_id>/document-requirements/bulk-add/',
         views.bulk_add_requirements,
         name='bulk_add_requirements'),

    path('api/applications/<int:application_id>/document-requirements/<int:document_type_id>/remove/',
         views.remove_document_requirement,
         name='remove_document_requirement'),

    path('api/applications/<int:application_id>/requirement-status/',
         views.get_requirement_status,
         name='get_requirement_status'),
]
