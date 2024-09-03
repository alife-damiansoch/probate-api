import os
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes, OpenApiResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import BytesIO
import json
from datetime import date

from core.models import Application, Solicitor, User  # Assuming these models are in the 'core' app


@extend_schema(
    summary="Generate an Undertaking PDF",
    description="Generates a PDF document for an undertaking based on the application ID and agreed fee provided in the request. This endpoint is intended for use by authorized users only.",
    tags=["undertaking"],
    request=OpenApiTypes.OBJECT,  # Expecting a generic object for request body
    examples=[
        OpenApiExample(
            name="Example request",
            value={
                "application_id": 180,
                "fee_agreed_for_undertaking": 37500
            },
            request_only=True,  # This example is only for the request body
        )
    ],
    responses={
        200: OpenApiResponse(
            description='Generated PDF file',
            response=OpenApiTypes.BINARY,  # Use OpenApiTypes.BINARY for binary file response
        ),
        400: OpenApiResponse(
            description='Bad Request',
            response=OpenApiTypes.OBJECT
        ),
        404: OpenApiResponse(
            description='Not Found',
            response=OpenApiTypes.OBJECT
        ),
        500: OpenApiResponse(
            description='Internal Server Error',
            response=OpenApiTypes.OBJECT
        ),
    }
)
@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def generate_undertaking_pdf(request):
    try:
        data = json.loads(request.body)
        application_id = data.get('application_id')
        fee_agreed_for_undertaking = data.get('fee_agreed_for_undertaking')

        # Fetch the application by its ID
        application = get_object_or_404(Application, id=application_id)

        # Get company details from environment variables using os.getenv
        company_name = os.getenv('COMPANY_NAME', 'Default Company Name')
        company_address = os.getenv('COMPANY_ADDRESS', 'Default Company Address')

        solicitor = application.solicitor  # Assuming `application` has a `solicitor` field
        user = solicitor.user if solicitor else None  # Fetch the User linked to the Solicitor

        # Get solicitor details
        solicitor_name = str(solicitor) if solicitor else "N/A"
        solicitor_firm_name = user.name if user else "N/A"  # Get the name from the User model
        solicitor_address_obj = user.address if user and user.address else None  # Get the address object from the User model

        # Format the solicitor address
        if solicitor_address_obj:
            solicitor_firm_address = f"{solicitor_address_obj.line1}, {solicitor_address_obj.line2}, {solicitor_address_obj.town_city}, {solicitor_address_obj.county}, {solicitor_address_obj.eircode.upper()}"
        else:
            solicitor_firm_address = "N/A"

        # Get all applicants associated with the application
        applicants = application.applicants.all()
        if applicants.exists():
            applicant_names = ', '.join([f"{applicant.first_name} {applicant.last_name}" for applicant in applicants])
        else:
            applicant_names = "N/A"

        # Prepare context data for the PDF generation
        context = {
            'application_id': application.id,
            'amount': application.amount,
            'term': application.term,
            'deceased_first_name': application.deceased.first_name if application.deceased else "N/A",
            'deceased_last_name': application.deceased.last_name if application.deceased else "N/A",
            'fee_agreed_for_undertaking': fee_agreed_for_undertaking,  # Use the fee from the request
            'dispute_details': application.dispute.details if application.dispute else "N/A",
            'solicitor_name': solicitor_name,
            'solicitor_firm_name': solicitor_firm_name,
            'solicitor_firm_address': solicitor_firm_address,
            'applicant_name': applicant_names,
            'current_date': date.today().strftime("%B %d, %Y"),  # Format the current date
            'company_name': company_name,
            'company_address': company_address,
        }

        # Render the HTML template with context data
        html_string = render_to_string('undertaking/undertaking_template.html', context)

        # Create a byte stream buffer
        result = BytesIO()
        # Generate PDF from the HTML string using xhtml2pdf
        pdf = pisa.CreatePDF(BytesIO(html_string.encode("UTF-8")), dest=result)

        # If there's an error generating the PDF, return an error response
        if pdf.err:
            return JsonResponse({'error': 'Error generating PDF'}, status=500)

        # Return PDF as a response
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="undertaking.pdf"'
        return response

    except Application.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
