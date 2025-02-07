from django.http import HttpResponseServerError

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now

from communications.utils import send_email_f

from django.conf import settings

logger = logging.getLogger(__name__)  # Use Django's logging system


def test_500_view(request):
    # This will cause a server error
    return HttpResponseServerError()


@csrf_exempt
def csp_report(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            report = data.get("csp-report", {})

            document_uri = report.get("document-uri", "Unknown")
            violated_directive = report.get("violated-directive", "Unknown")
            blocked_uri = report.get("blocked-uri", "Unknown")
            source_file = report.get("source-file", "Unknown")
            line_number = report.get("line-number", "N/A")

            # Construct email message
            subject = "🚨 CSP Violation Detected"
            message = f"""
            <h3>A CSP violation was detected on your website.</h3>
            <p><strong>Timestamp:</strong> {now()}</p>
            <p><strong>Document:</strong> {document_uri}</p>
            <p><strong>Violated Directive:</strong> {violated_directive}</p>
            <p><strong>Blocked URI:</strong> {blocked_uri}</p>
            <p><strong>Source File:</strong> {source_file}</p>
            <p><strong>Line Number:</strong> {line_number}</p>
            """

            admin_emails = settings.ADMIN_EMAILS

            for email in admin_emails:
                # Send email with details
                send_email_f(
                    sender="noreply@alife.ie",
                    recipient=email,
                    subject=subject,
                    message=message,
                    save_in_email_log=False
                )

            return JsonResponse({"status": "success"}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)
