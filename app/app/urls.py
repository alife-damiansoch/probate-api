from django.contrib import admin
from django.urls import (path, include)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView
)
from django.conf.urls.static import static
from django.conf import settings

from core.views import test_500_view, csp_report
from app.settings import ADMIN_URL

urlpatterns = [
    path(f'{ADMIN_URL}/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/docs/',
         SpectacularSwaggerView.as_view(url_name="api-schema"),
         name='api-docs'),
    path('api/user/', include('user.urls')),
    path('api/', include('solicitors_loan.urls', namespace='solicitors_loan')),
    path('api/', include('agents_loan.urls', namespace='agents_loan')),
    path('api/', include('event.urls', namespace='event')),
    path('api/', include('comment.urls', namespace='comment')),
    path('api/', include('expense.urls', namespace='expense')),
    path('api/', include('loan.urls', namespace='loan')),
    path('api/', include('notifications.urls', namespace='notification')),
    path('api/', include('assigned_solicitor.urls', namespace='assigned_solicitor')),
    path('api/', include('undertaking.urls', namespace='undertaking')),
    path('api/downloadableFiles/', include('downloadableFiles.urls', namespace='downloadableFiles')),
    path('api/signed_documents/', include('signed_documents.urls', namespace='signed_documents')),
    path('api/assignments/', include('agents_default_assignments.urls', namespace='assignments')),
    path('api/', include('communications.urls', namespace='communications')),

    # test and security paths from core app
    path('test/500/', test_500_view),
    path("csp-report/", csp_report, name="csp_report"),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
