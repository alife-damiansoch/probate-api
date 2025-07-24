# esignature/urls.py
from django.urls import path
from . import views

app_name = 'esignature'

urlpatterns = [
    # Document management
    path('documents/', views.SignatureDocumentListCreateView.as_view(), name='document-list-create'),
    path('documents/<uuid:pk>/', views.SignatureDocumentDetailView.as_view(), name='document-detail'),

    # Signer management
    path('documents/<uuid:document_id>/signers/', views.DocumentSignerListCreateView.as_view(),
         name='signer-list-create'),
    path('signers/<uuid:pk>/', views.DocumentSignerDetailView.as_view(), name='signer-detail'),

    # Field management
    path('documents/<uuid:document_id>/fields/', views.SignatureFieldListCreateView.as_view(),
         name='field-list-create'),
    path('fields/<uuid:pk>/', views.SignatureFieldDetailView.as_view(), name='field-detail'),

    # Signing process
    path('documents/<uuid:document_id>/start-signing/', views.StartSigningProcessView.as_view(), name='start-signing'),
    path('documents/<uuid:document_id>/cancel-signing/', views.CancelDocumentSigningView.as_view(),
         name='cancel-signing'),
    path('documents/<uuid:document_id>/status/', views.DocumentSigningStatusView.as_view(), name='signing-status'),

    # Field signing
    path('sign-fields/', views.BulkSignFieldsView.as_view(), name='bulk-sign-fields'),

    # Access control
    path('documents/<uuid:document_id>/signers/<uuid:signer_id>/access/', views.check_signing_access,
         name='check-access'),
]
