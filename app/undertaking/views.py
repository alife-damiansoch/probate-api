import datetime
import os
import zipfile

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
import datetime

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
            'current_date': datetime.date.today().strftime("%B %d, %Y"),  # Format the current date
            'company_name': company_name,
            'company_address': company_address,
            'currency_sign': application.user.get_currency()
        }

        print(context)

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


@extend_schema(
    summary="Generate an Advancement Agreement PDF",
    description="Generates a PDF document for a single applicant or multiple PDF documents bundled in a ZIP for multiple applicants based on the application ID and agreed fee provided in the request.",
    tags=["advancement"],
    request=OpenApiTypes.OBJECT,
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
            description='Generated PDF or ZIP file',
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
def generate_advancement_agreement_pdf(request):
    try:
        data = json.loads(request.body)
        application_id = data.get('application_id')
        fee_agreed_for_undertaking = data.get('fee_agreed_for_undertaking')

        # Fetch the application by its ID
        application = get_object_or_404(Application, id=application_id)

        # Get company details from environment variables using os.getenv
        company_name = os.getenv('COMPANY_NAME', 'Default Company Name')
        company_address = os.getenv('COMPANY_ADDRESS', 'Default Company Address')
        company_registration_number = os.getenv('COMPANY_REGISTRATION_NUMBER', 'Default Registration Number')
        company_website = os.getenv('COMPANY_WEBSITE', 'https://example.com')
        company_phone_number = os.getenv('COMPANY_PHONE_NUMBER', '012345678')
        company_ceo = os.getenv('COMPANY_CEO', 'default CEO')

        # Get all applicants associated with the application
        applicants = application.applicants.all()

        # Check if there's only one applicant, then return a single PDF
        if len(applicants) == 1:
            # Single applicant case
            applicant = applicants[0]
            # Create PDF for the single applicant
            pdf_response = create_pdf_for_applicant(application, applicant, company_name, company_address,
                                                    company_registration_number, company_website, company_phone_number,
                                                    fee_agreed_for_undertaking, company_ceo)
            response = HttpResponse(pdf_response.getvalue(), content_type='application/pdf')
            response[
                'Content-Disposition'] = f'attachment; filename="Advancement_Agreement_{application_id}_{applicant.first_name}_{applicant.last_name}.pdf"'
            return response

        # If there are multiple applicants, create a ZIP archive
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for applicant in applicants:
                pdf_response = create_pdf_for_applicant(application, applicant, company_name, company_address,
                                                        company_registration_number, company_website,
                                                        company_phone_number,
                                                        fee_agreed_for_undertaking, company_ceo)
                pdf_filename = f"Advancement_Agreement_{application_id}_{applicant.first_name}_{applicant.last_name}.pdf"
                zip_file.writestr(pdf_filename, pdf_response.getvalue())

        # Return the ZIP file as a response
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="Advancement_Agreements_{application_id}.zip"'
        return response

    except Application.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def create_pdf_for_applicant(application, applicant, company_name, company_address, company_registration_number,
                             company_website, company_phone_number, fee_agreed_for_undertaking, company_ceo):
    """
    Helper function to create a PDF for a single applicant.
    """
    # Get individual applicant details
    applicant_name = f"{applicant.first_name} {applicant.last_name}"
    applicant_pps = applicant.pps_number if hasattr(applicant, 'pps_number') else "N/A"

    # Calculate the advancement details based on application data and fee
    advancement_amount = application.amount  # Assuming 'amount' field in Application model
    advancement_term = application.term  # Assuming 'term' field in Application model
    interest_rate = 15  # Assuming 'interest_rate' field in Application model
    total_amount_payable = float(advancement_amount) + float(fee_agreed_for_undertaking)
    total_interest = fee_agreed_for_undertaking
    cost_per_100 = round((float(total_interest) / float(advancement_amount)) * 100, 2) if advancement_amount else 0
    apr = 15  # Using interest rate as APR if both are equal

    # Prepare context data for the PDF generation
    context = {
        # company details
        'company_name': company_name,
        'company_registration_number': company_registration_number,
        'company_address': company_address,
        'company_website': company_website,
        'company_phone_number': company_phone_number,
        'company_ceo': company_ceo,
        # applicant details
        'applicant_name': applicant_name,
        'applicant_pps': applicant_pps.upper(),
        # application details
        'agreement_number': application.id,
        'advancement_amount': advancement_amount,
        'advancement_term': advancement_term,
        'total_amount_payable': total_amount_payable,
        'total_interest': total_interest,
        'apr': apr,
        'interest_rate': interest_rate,
        'cost_per_100': cost_per_100,
        'current_year': datetime.date.today().year,
        'currency_sign': application.user.get_currency(),
        # date
        'today_date': datetime.datetime.now().strftime("%d/%m/%Y"),
        'current_year ': datetime.datetime.now().strftime("%Y")
    }

    # Render the HTML template for the applicant
    html_string = render_to_string('advancement_agreement/advanced_agreement_template.html', context)

    # Create a byte stream buffer for the PDF
    pdf_buffer = BytesIO()
    # Generate PDF from the HTML string using xhtml2pdf
    pdf = pisa.CreatePDF(BytesIO(html_string.encode("UTF-8")), dest=pdf_buffer)

    if pdf.err:
        raise Exception('Error generating PDF')

    return pdf_buffer
