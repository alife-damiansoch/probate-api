import datetime
import os
import zipfile

from django.forms import model_to_dict
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes, OpenApiResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import BytesIO
import json
import datetime

from core.models import Application, Solicitor, User, Document  # Added Document model
from loanbook.models import LoanBook


@extend_schema(
    summary="Generate an Undertaking PDF",
    description="Generates a PDF document for an undertaking based on the application ID and agreed fee provided in the request. The PDF is saved directly to the application's documents with signature requirements.",
    tags=["undertaking"],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            name="Example request",
            value={
                "application_id": 180,
                "fee_agreed_for_undertaking": 37500
            },
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            description='PDF generated and saved successfully',
            response=OpenApiTypes.OBJECT
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

        # Render the HTML template with context data
        html_string = render_to_string('undertaking/undertaking_template.html', context)

        # Create a byte stream buffer
        result = BytesIO()
        # Generate PDF from the HTML string using xhtml2pdf
        pdf = pisa.CreatePDF(BytesIO(html_string.encode("UTF-8")), dest=result)

        # If there's an error generating the PDF, return an error response
        if pdf.err:
            return JsonResponse({'error': 'Error generating PDF'}, status=500)

        # Get the PDF content
        pdf_content = result.getvalue()

        # Create a filename for the PDF
        filename = f"Solicitor_Undertaking_{application_id}.pdf"

        # Create a Document instance and save the PDF with signature requirements
        document = Document(
            application=application,
            is_signed=False,
            is_undertaking=True,
            is_loan_agreement=False,
            signature_required=True,  # Undertaking requires signature
            who_needs_to_sign='solicitor'  # Solicitor needs to sign undertaking
        )

        # Save the PDF file to the document field
        document.document.save(
            filename,
            ContentFile(pdf_content),
            save=False
        )

        # Save the document instance
        document.save()

        return JsonResponse({
            'success': True,
            'message': 'Undertaking PDF generated and saved successfully. Solicitor signature required.',
            'document_id': document.id,
            'filename': filename,
            'signature_required': True,
            'who_needs_to_sign': 'solicitor'
        })

    except Application.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@extend_schema(
    summary="Generate an Advancement Agreement PDF",
    description="Generates PDF documents for advancement agreements and saves them directly to the application's documents. Creates separate PDFs for each applicant with signature requirements and saves them individually.",
    tags=["advancement"],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            name="Example request",
            value={
                "application_id": 180,
                "fee_agreed_for_undertaking": 37500
            },
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            description='PDFs generated and saved successfully',
            response=OpenApiTypes.OBJECT
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

        created_documents = []

        # Create a PDF for each applicant and save as Document
        for applicant in applicants:
            pdf_response = create_pdf_for_applicant(application, applicant, company_name, company_address,
                                                    company_registration_number, company_website,
                                                    company_phone_number, fee_agreed_for_undertaking, company_ceo)

            # Create filename with the specified format
            filename = f"Advancement_Agreement_{application_id}_{applicant.first_name}_{applicant.last_name}.pdf"

            # Create a Document instance and save the PDF with signature requirements
            document = Document(
                application=application,
                is_signed=False,
                is_undertaking=False,
                is_loan_agreement=True,
                signature_required=True,  # Advancement agreement requires signature
                who_needs_to_sign='applicant'  # Applicant needs to sign advancement agreement
            )

            # Save the PDF file to the document field
            document.document.save(
                filename,
                ContentFile(pdf_response.getvalue()),
                save=False
            )

            # Save the document instance
            document.save()

            created_documents.append({
                'document_id': document.id,
                'filename': filename,
                'applicant_name': f"{applicant.first_name} {applicant.last_name}",
                'signature_required': True,
                'who_needs_to_sign': 'applicant'
            })

        return JsonResponse({
            'success': True,
            'message': f'Advancement Agreement PDFs generated and saved successfully for {len(applicants)} applicant(s). Applicant signatures required.',
            'documents': created_documents,
            'total_documents_created': len(created_documents)
        })

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
    applicant_pps = applicant.decrypted_pps if hasattr(applicant, 'decrypted_pps') else "N/A"

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


@extend_schema(
    summary="Generate Terms of Business PDF",
    description="Generates a PDF document for Terms of Business based on the application ID. This is an informational document that does not require signature and must be provided before any credit agreement is signed.",
    tags=["terms-of-business"],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            name="Example request",
            value={
                "application_id": 180
            },
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            description='Terms of Business PDF generated and saved successfully',
            response=OpenApiTypes.OBJECT
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
def generate_terms_of_business_pdf(request):
    try:
        data = json.loads(request.body)
        application_id = data.get('application_id')

        # Fetch the application by its ID
        application = get_object_or_404(Application, id=application_id)

        # Get company details from environment variables using os.getenv
        company_name = os.getenv('COMPANY_NAME', 'Default Company Name')
        company_address = os.getenv('COMPANY_ADDRESS', 'Default Company Address')
        company_registration_number = os.getenv('COMPANY_REGISTRATION_NUMBER', 'Default Registration Number')
        company_website = os.getenv('COMPANY_WEBSITE', 'https://example.com')
        company_phone_number = os.getenv('COMPANY_PHONE_NUMBER', '012345678')
        company_email = os.getenv('COMPANY_EMAIL', 'info@company.com')
        company_ceo = os.getenv('COMPANY_CEO', 'Default CEO')

        # Additional company details you might need
        company_fax = os.getenv('COMPANY_FAX', '012345679')
        company_vat_number = os.getenv('COMPANY_VAT_NUMBER', 'IE1234567X')
        company_license_number = os.getenv('COMPANY_LICENSE_NUMBER', 'ML001234')

        solicitor = application.solicitor
        user = solicitor.user if solicitor else None

        # Get solicitor details
        solicitor_name = str(solicitor) if solicitor else "N/A"
        solicitor_firm_name = user.name if user else "N/A"
        solicitor_address_obj = user.address if user and user.address else None

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
            'solicitor_name': solicitor_name,
            'solicitor_firm_name': solicitor_firm_name,
            'solicitor_firm_address': solicitor_firm_address,
            'applicant_names': applicant_names,
            'current_date': datetime.date.today().strftime("%B %d, %Y"),
            'current_year': datetime.date.today().year,
            'currency_sign': application.user.get_currency(),

            # Company details
            'company_name': company_name,
            'company_address': company_address,
            'company_registration_number': company_registration_number,
            'company_website': company_website,
            'company_phone_number': company_phone_number,
            'company_email': company_email,
            'company_fax': company_fax,
            'company_vat_number': company_vat_number,
            'company_license_number': company_license_number,
            'company_ceo': company_ceo,
        }

        # Render the HTML template with context data
        html_string = render_to_string('terms_of_business/terms_of_business_template.html', context)

        # Create a byte stream buffer
        result = BytesIO()
        # Generate PDF from the HTML string using xhtml2pdf
        pdf = pisa.CreatePDF(BytesIO(html_string.encode("UTF-8")), dest=result)

        # If there's an error generating the PDF, return an error response
        if pdf.err:
            return JsonResponse({'error': 'Error generating PDF'}, status=500)

        # Get the PDF content
        pdf_content = result.getvalue()

        # Create a filename for the PDF
        filename = f"Terms_of_Business_{application_id}.pdf"

        # Create a Document instance and save the PDF (no signature required)
        document = Document(
            application=application,
            is_signed=False,
            is_undertaking=False,
            is_loan_agreement=False,
            is_terms_of_business=True,  # New field
            signature_required=False,  # Terms of Business don't require signature
            who_needs_to_sign='solicitor'  # Default value, not used since no signature required
        )

        # Save the PDF file to the document field
        document.document.save(
            filename,
            ContentFile(pdf_content),
            save=False
        )

        # Save the document instance
        document.save()

        return JsonResponse({
            'success': True,
            'message': 'Terms of Business PDF generated and saved successfully. No signature required.',
            'document_id': document.id,
            'filename': filename,
            'signature_required': False,
            'document_type': 'terms_of_business'
        })

    except Application.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@extend_schema(
    summary="Generate SECCI Form PDF",
    description="Generates a PDF document for SECCI (Standard European Consumer Credit Information) form based on the application ID. This is a mandatory pre-contractual document under EU Consumer Credit Directive that does not require signature.",
    tags=["secci"],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            name="Example request",
            value={
                "application_id": 180,
                "fee_agreed_for_undertaking": 37500
            },
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            description='SECCI Form PDF generated and saved successfully',
            response=OpenApiTypes.OBJECT
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
@extend_schema(
    summary="Generate SECCI Form PDF",
    description="Generates a PDF document for SECCI (Standard European Consumer Credit Information) form based on the application ID. This is a mandatory pre-contractual document under EU Consumer Credit Directive that does not require signature.",
    tags=["secci"],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            name="Example request",
            value={
                "application_id": 180,
                "fee_agreed_for_undertaking": 37500
            },
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            description='SECCI Form PDF generated and saved successfully',
            response=OpenApiTypes.OBJECT
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
@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def generate_secci_pdf(request):
    try:
        data = json.loads(request.body)
        application_id = data.get('application_id')
        fee_agreed_for_undertaking = data.get('fee_agreed_for_undertaking')

        # Fetch the application by its ID
        application = get_object_or_404(Application, id=application_id)

        # Get company details from environment variables
        company_name = os.getenv('COMPANY_NAME', 'Default Company Name')
        company_address = os.getenv('COMPANY_ADDRESS', 'Default Company Address')
        company_registration_number = os.getenv('COMPANY_REGISTRATION_NUMBER', 'Default Registration Number')
        company_phone_number = os.getenv('COMPANY_PHONE_NUMBER', '012345678')
        company_email = os.getenv('COMPANY_EMAIL', 'info@company.com')
        company_website = os.getenv('COMPANY_WEBSITE', 'https://example.com')

        # Get applicant details
        applicants = application.applicants.all()
        if applicants.exists():
            applicant_names = ', '.join([f"{applicant.first_name} {applicant.last_name}" for applicant in applicants])
            first_applicant = applicants.first()
            applicant_name = f"{first_applicant.first_name} {first_applicant.last_name}"
        else:
            applicant_names = "N/A"
            applicant_name = "N/A"

        # Calculate probate advancement details using LoanBook calculation method
        # Convert to Decimal to match LoanBook calculation expectations
        from decimal import Decimal
        advancement_amount = Decimal(str(application.amount))
        advancement_term = max(12, min(application.term, 36))  # Ensure between 12-36 months

        # Use LoanBook calculation method for accurate costs
        scenarios = LoanBook.calculate_secci_scenarios(advancement_amount)

        min_scenario = scenarios['minimum']
        max_scenario = scenarios['maximum']
        fee_percentages = scenarios['fee_percentages']

        # Calculate representative APR for this specific application term
        if advancement_term > 0:
            representative_scenario = LoanBook.calculate_probate_costs(
                advancement_amount,
                fee_percentages['initial_fee_percentage'],
                fee_percentages['daily_fee_percentage'],
                fee_percentages['exit_fee_percentage'],
                advancement_term
            )
            # Convert all to Decimal for consistent calculation
            total_cost_decimal = representative_scenario['total_cost']
            advancement_amount_decimal = representative_scenario['initial_amount']
            advancement_term_decimal = Decimal(str(advancement_term))
            twelve_decimal = Decimal('12')
            hundred_decimal = Decimal('100')

            # APR calculation with all Decimal types
            apr_decimal = (total_cost_decimal / advancement_amount_decimal) * (
                    twelve_decimal / advancement_term_decimal) * hundred_decimal
            apr = float(round(apr_decimal, 1))
        else:
            apr = 0

        # Prepare context data for the PDF generation
        context = {
            'application_id': application.id,
            'current_date': datetime.date.today().strftime("%d/%m/%Y"),
            'current_year': datetime.date.today().year,
            'currency_sign': application.user.get_currency(),

            # Company details
            'company_name': company_name,
            'company_address': company_address,
            'company_registration_number': company_registration_number,
            'company_phone_number': company_phone_number,
            'company_email': company_email,
            'company_website': company_website,

            # Applicant details
            'applicant_name': applicant_name,
            'applicant_names': applicant_names,

            # Credit details - FORMAT THESE NUMBERS
            'credit_amount': f"{float(advancement_amount):,.0f}",  # Format with commas
            'credit_term': advancement_term,

            # Fee structure
            'initial_fee_percentage': f"{float(fee_percentages['initial_fee_percentage']):.2f}",
            'daily_fee_percentage': f"{float(fee_percentages['daily_fee_percentage']):.2f}",
            'exit_fee_percentage': f"{float(fee_percentages['exit_fee_percentage']):.2f}",

            # Minimum scenario (12 months) - FORMAT THESE
            'first_year_charge': f"{float(min_scenario['first_year_charge']):,.0f}",
            'minimum_exit_fee': f"{float(min_scenario['exit_fee']):,.0f}",
            'minimum_total_cost': f"{float(min_scenario['total_cost']):,.0f}",
            'minimum_payable': f"{float(min_scenario['total_payable']):,.0f}",

            # Maximum scenario (36 months) - FORMAT THESE
            'maximum_daily_interest': f"{float(max_scenario['daily_interest_total']):,.0f}",
            'maximum_exit_fee': f"{float(max_scenario['exit_fee']):,.0f}",
            'maximum_total_cost': f"{float(max_scenario['total_cost']):,.0f}",
            'maximum_payable': f"{float(max_scenario['total_payable']):,.0f}",

            # APR
            'apr': f"{apr:.1f}",

            # Dates
            'agreement_date': datetime.date.today().strftime("%d/%m/%Y"),
            'first_payment_date': "When probate is granted",
            'final_payment_date': (datetime.date.today() + datetime.timedelta(days=30 * advancement_term)).strftime(
                "%d/%m/%Y"),
        }

        # Render the HTML template with context data
        html_string = render_to_string('secci/secci_template.html', context)

        # Create a byte stream buffer
        result = BytesIO()
        # Generate PDF from the HTML string using xhtml2pdf
        pdf = pisa.CreatePDF(BytesIO(html_string.encode("UTF-8")), dest=result)

        # If there's an error generating the PDF, return an error response
        if pdf.err:
            return JsonResponse({'error': 'Error generating PDF'}, status=500)

        # Get the PDF content
        pdf_content = result.getvalue()

        # Create a filename for the PDF
        filename = f"SECCI_Form_{application_id}.pdf"

        # Create a Document instance and save the PDF (no signature required)
        document = Document(
            application=application,
            is_signed=False,
            is_undertaking=False,
            is_loan_agreement=False,
            is_secci=True,  # Assuming you have this field
            signature_required=False,  # SECCI forms don't require signature
            who_needs_to_sign='solicitor'  # Default value, not used since no signature required
        )

        # Save the PDF file to the document field
        document.document.save(
            filename,
            ContentFile(pdf_content),
            save=False
        )

        # Save the document instance
        document.save()

        return JsonResponse({
            'success': True,
            'message': 'SECCI Form PDF generated and saved successfully. No signature required.',
            'document_id': document.id,
            'filename': filename,
            'signature_required': False,
            'document_type': 'secci'
        })

    except Application.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
