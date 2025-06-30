from datetime import datetime

from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import Http404, HttpResponse
from drf_spectacular.utils import extend_schema

from core.models import InternalFile
from .serializers import InternalFileSerializer
from agents_loan.permissions import IsStaff  # Adjust import path
from core.models import Application  # Adjust import path

import os
import shutil
import requests
from django.conf import settings


class InternalFileListView(APIView):
    """
    List internal files for a specific application or all files.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    serializer_class = InternalFileSerializer

    @extend_schema(
        summary="List internal files",
        description="Retrieve internal files. Optionally filter by application_id. Staff only.",
        tags=["internal_files"],
        parameters=[
            {
                'name': 'application_id',
                'in': 'query',
                'description': 'Filter files by application ID',
                'required': False,
                'schema': {'type': 'integer'}
            }
        ]
    )
    def get(self, request):
        application_id = request.query_params.get('application_id')
        print(f"DEBUG: Received application_id: {application_id}")

        if application_id:
            files = InternalFile.objects.filter(
                application_id=application_id,
                is_active=True
            )
            print(f"DEBUG: Found {files.count()} files for application {application_id}")
            print(f"DEBUG: Files: {list(files.values())}")
        else:
            files = InternalFile.objects.filter(is_active=True)
            print(f"DEBUG: Found {files.count()} total active files")

        serializer = self.serializer_class(files, many=True)
        print(f"DEBUG: Serialized data: {serializer.data}")
        return Response(serializer.data)


class InternalFileCreateView(APIView):
    """
    Create internal file for a specific application.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    serializer_class = InternalFileSerializer

    def get_application(self, application_id):
        try:
            return Application.objects.get(id=application_id)
        except Application.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Create internal file for application",
        description="Upload a new internal file for a specific application. Staff only.",
        tags=["internal_files"],
    )
    def post(self, request, application_id):
        application = self.get_application(application_id)

        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(
                uploaded_by=request.user,
                application=application,
                is_active=True
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InternalFileDetailView(APIView):
    """
    Retrieve, update or delete an internal file.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    serializer_class = InternalFileSerializer

    def get_object(self, pk):
        try:
            return InternalFile.objects.get(pk=pk)
        except InternalFile.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Retrieve internal file details",
        description="Get details of a specific internal file. Staff only.",
        tags=["internal_files"],
    )
    def get(self, request, pk):
        file_obj = self.get_object(pk)
        serializer = self.serializer_class(file_obj)
        return Response(serializer.data)

    @extend_schema(
        summary="Update internal file",
        description="Update an existing internal file. Staff only.",
        tags=["internal_files"],
    )
    def patch(self, request, pk):
        file_obj = self.get_object(pk)
        serializer = self.serializer_class(file_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Delete internal file",
        description="Soft delete an internal file by setting is_active to False. Staff only.",
        tags=["internal_files"],
    )
    def delete(self, request, pk):
        file_obj = self.get_object(pk)

        if file_obj.file:
            try:
                # Get the current file path
                current_file_path = file_obj.file.path

                # Create the deleted files directory structure
                deleted_files_dir = os.path.join(settings.MEDIA_ROOT, 'deletedFiles', str(file_obj.application.id))

                # Create directory if it doesn't exist
                os.makedirs(deleted_files_dir, exist_ok=True)

                # Get the original filename
                original_filename = os.path.basename(current_file_path)

                # Create the destination path
                destination_path = os.path.join(deleted_files_dir, original_filename)

                # Handle filename conflicts by adding a timestamp or counter
                counter = 1
                base_name, extension = os.path.splitext(original_filename)
                while os.path.exists(destination_path):
                    new_filename = f"{base_name}_{counter}{extension}"
                    destination_path = os.path.join(deleted_files_dir, new_filename)
                    counter += 1

                # Move the file
                shutil.move(current_file_path, destination_path)

                print(f"DEBUG: File moved from {current_file_path} to {destination_path}")

            except Exception as e:
                print(f"ERROR: Failed to move file: {str(e)}")
                # You might want to decide whether to continue with deletion or return an error
                # For now, we'll continue with the deletion

        # Delete the database record (hard delete)
        file_obj.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class InternalFileDownloadView(APIView):
    """
    Download an internal file.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary="Download internal file",
        description="Download an internal file. Staff only.",
        tags=["internal_files"],
    )
    def get(self, request, pk):
        try:
            file_obj = InternalFile.objects.get(pk=pk, is_active=True)
            response = HttpResponse(
                file_obj.file.read(),
                content_type='application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{file_obj.file.name}"'
            return response
        except InternalFile.DoesNotExist:
            raise Http404


class PEPCheckCreateView(APIView):
    """
    Create PEP check for a specific application.
    Automatically runs dilisense API check and generates a report document.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def get_application(self, application_id):
        try:
            return Application.objects.get(id=application_id)
        except Application.DoesNotExist:
            raise Http404("Application not found")

    def get_applicant(self, application):
        """Get the first applicant for the application"""
        applicant = application.applicants.first()
        if not applicant:
            raise Http404("No applicant found for this application")
        return applicant

    def call_dilisense_api(self, applicant_name):
        """Call dilisense API to check for PEP/sanctions"""
        api_key = getattr(settings, 'DILISENSE_API_KEY', None)
        if not api_key:
            raise ValueError("DILISENSE_API_KEY not configured in settings")

        url = "https://api.dilisense.com/v1/checkIndividual"
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json'
        }
        params = {
            'names': applicant_name,
            'fuzzy': 'true'  # Enable fuzzy matching for better results
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            # Handle quota exceeded / payment required
            if response.status_code == 429:
                raise ValueError("API quota exceeded. Please upgrade your dilisense plan to continue PEP screening.")

            # Handle other client errors
            if response.status_code == 401:
                raise ValueError("Invalid API key. Please check your dilisense API configuration.")

            if response.status_code == 403:
                raise ValueError("API access forbidden. Please check your dilisense account status.")

            # Handle payment/subscription issues
            if response.status_code == 402:
                raise ValueError("Payment required. Your dilisense subscription needs to be renewed.")

            response.raise_for_status()

            # Parse response
            api_data = response.json()

            # Check for error messages in response body
            if 'error' in api_data:
                error_msg = api_data.get('error', 'Unknown API error')
                if 'quota' in error_msg.lower() or 'limit' in error_msg.lower():
                    raise ValueError(
                        "API quota exceeded. Please upgrade your dilisense plan to continue PEP screening.")
                elif 'payment' in error_msg.lower() or 'subscription' in error_msg.lower():
                    raise ValueError("Payment required. Your dilisense subscription needs to be renewed.")
                else:
                    raise ValueError(f"API Error: {error_msg}")

            return api_data

        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 429:
                    raise ValueError(
                        "API quota exceeded. Please upgrade your dilisense plan to continue PEP screening.")
                elif e.response.status_code == 402:
                    raise ValueError("Payment required. Your dilisense subscription needs to be renewed.")
                else:
                    raise ValueError(f"Failed to connect to dilisense API: HTTP {e.response.status_code}")
            else:
                raise ValueError(f"Failed to connect to dilisense API: {str(e)}")

    def generate_pep_report_content(self, applicant, api_response, check_timestamp):
        """Generate HTML content for the PEP check report"""
        total_hits = api_response.get('total_hits', 0)
        found_records = api_response.get('found_records', [])

        # Determine status
        if total_hits == 0:
            status_color = "green"
            status_text = "CLEAR"
            risk_level = "LOW RISK"
        else:
            status_color = "red"
            status_text = "MATCH FOUND"
            risk_level = "HIGH RISK - REQUIRES REVIEW"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PEP & Sanctions Check Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .status-clear {{ color: green; font-weight: bold; }}
        .status-match {{ color: red; font-weight: bold; }}
        .section {{ margin-bottom: 20px; }}
        .match-record {{ background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 10px 0; }}
        .risk-high {{ background-color: #f8d7da; padding: 10px; border-radius: 5px; }}
        .risk-low {{ background-color: #d4edda; padding: 10px; border-radius: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>PEP & Sanctions Screening Report</h1>
        <p><strong>Application ID:</strong> {applicant.application.id}</p>
        <p><strong>Check Date:</strong> {check_timestamp}</p>
        <p><strong>Checked By:</strong> System Automated Check</p>
    </div>

    <div class="section">
        <h2>Applicant Information</h2>
        <table>
            <tr><th>Title</th><td>{applicant.title}</td></tr>
            <tr><th>First Name</th><td>{applicant.first_name}</td></tr>
            <tr><th>Last Name</th><td>{applicant.last_name}</td></tr>
            <tr><th>Date of Birth</th><td>{applicant.date_of_birth or 'Not provided'}</td></tr>
            <tr><th>Address</th><td>{applicant.address_line_1}, {applicant.city}, {applicant.county}, {applicant.country}</td></tr>
            <tr><th>Email</th><td>{applicant.email or 'Not provided'}</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>Screening Results</h2>
        <div class="{'risk-high' if total_hits > 0 else 'risk-low'}">
            <p><strong>Status:</strong> <span class="{'status-match' if total_hits > 0 else 'status-clear'}">{status_text}</span></p>
            <p><strong>Risk Level:</strong> {risk_level}</p>
            <p><strong>Total Matches Found:</strong> {total_hits}</p>
        </div>
    </div>

    <div class="section">
        <h2>Screening Details</h2>
        <p><strong>Searched Name:</strong> {applicant.first_name} {applicant.last_name}</p>
        <p><strong>Search Type:</strong> Individual PEP & Sanctions Check</p>
        <p><strong>Fuzzy Matching:</strong> Enabled</p>
        <p><strong>Database Coverage:</strong> OFAC, EU, UN, PEP Lists, Criminal Watchlists</p>
    </div>
"""

        if total_hits > 0:
            html_content += """
    <div class="section">
        <h2>Match Details - REQUIRES MANUAL REVIEW</h2>
        <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
            <strong>⚠️ WARNING: Potential matches found. This application requires immediate manual review before proceeding.</strong>
        </div>
"""
            for i, record in enumerate(found_records, 1):
                html_content += f"""
        <div class="match-record">
            <h3>Match #{i}</h3>
            <table>
                <tr><th>Name</th><td>{record.get('name', 'N/A')}</td></tr>
                <tr><th>Entity Type</th><td>{record.get('entity_type', 'N/A')}</td></tr>
                <tr><th>Date of Birth</th><td>{', '.join(record.get('date_of_birth', []) or ['N/A'])}</td></tr>
                <tr><th>Citizenship</th><td>{', '.join(record.get('citizenship', []) or ['N/A'])}</td></tr>
                <tr><th>Aliases</th><td>{', '.join(record.get('alias_names', []) or ['None'])}</td></tr>
                <tr><th>Positions</th><td>{', '.join(record.get('positions', []) or ['N/A'])}</td></tr>
            </table>

            <h4>Sources:</h4>
            <ul>
"""
                for source in record.get('sources', []):
                    html_content += f"""
                <li><strong>{source.get('name', 'Unknown Source')}</strong> ({source.get('country_name', 'N/A')})<br>
                    <em>{source.get('description', 'No description available')}</em></li>
"""
                html_content += """
            </ul>
        </div>
"""
        else:
            html_content += """
    <div class="section">
        <h2>Clear Result</h2>
        <div style="background-color: #d4edda; padding: 15px; border-radius: 5px;">
            <strong>✅ No matches found in PEP, sanctions, or criminal watchlists.</strong>
            <p>The applicant does not appear on any of the screened lists and can proceed with the application process.</p>
        </div>
    </div>
"""

        html_content += f"""
    <div class="section">
        <h2>Technical Details</h2>
        <table>
            <tr><th>API Response Timestamp</th><td>{api_response.get('timestamp', 'N/A')}</td></tr>
            <tr><th>Search Provider</th><td>dilisense AML Screening API</td></tr>
            <tr><th>Response Status</th><td>Success</td></tr>
        </table>
    </div>

    <div class="footer">
        <p><strong>Disclaimer:</strong> This report is generated automatically based on publicly available sanctions, PEP, and criminal watchlists. 
        Manual review may be required for any matches found. This screening was performed in compliance with AML/KYC regulations.</p>

        <p><strong>Next Steps:</strong> 
        {'Manual review and enhanced due diligence required before proceeding with application.' if total_hits > 0 else 'Application may proceed to next stage.'}
        </p>

        <p><strong>Generated:</strong> {check_timestamp} | <strong>System:</strong> Automated PEP/Sanctions Screening</p>
    </div>
</body>
</html>
"""
        return html_content

    @extend_schema(
        summary="Create PEP check for application",
        description="Automatically run PEP/sanctions check for application's first applicant and generate report document. Staff only.",
        tags=["pep_checks"],
    )
    def post(self, request, application_id):
        try:
            # Get application and applicant
            application = self.get_application(application_id)
            applicant = self.get_applicant(application)

            # Check if PEP check already exists for this application
            existing_pep_check = InternalFile.objects.filter(
                application=application,
                is_pep_check=True,
                is_active=True
            ).first()

            if existing_pep_check:
                return Response(
                    {"error": "PEP check already exists for this application",
                     "existing_file_id": existing_pep_check.id},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Prepare applicant name for API call
            applicant_name = f"{applicant.first_name} {applicant.last_name}".strip()
            check_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            # Call dilisense API
            try:
                api_response = self.call_dilisense_api(applicant_name)
            except ValueError as e:
                return Response(
                    {"error": f"API call failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Generate report content
            report_content = self.generate_pep_report_content(applicant, api_response, check_timestamp)

            # Create filename
            filename = f"PEP_Check_Report_{application.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

            # Create InternalFile instance
            internal_file = InternalFile(
                title=f"PEP Check Report - Application {application.id}",
                description=f"Automated PEP/Sanctions screening report for {applicant_name}. "
                            f"Status: {'MATCH FOUND - REQUIRES REVIEW' if api_response.get('total_hits', 0) > 0 else 'CLEAR'}. "
                            f"Total hits: {api_response.get('total_hits', 0)}. "
                            f"Generated on {check_timestamp}.",
                application=application,
                uploaded_by=request.user,
                is_active=True,
                is_ccr=False,  # This is not a CCR
                is_pep_check=True  # This is a PEP check
            )

            # Save HTML content as file
            internal_file.file.save(
                filename,
                ContentFile(report_content.encode('utf-8')),
                save=False
            )

            internal_file.save()

            # Prepare response data
            response_data = {
                "success": True,
                "message": "PEP check completed successfully",
                "file_id": internal_file.id,
                "application_id": application.id,
                "applicant_name": applicant_name,
                "total_hits": api_response.get('total_hits', 0),
                "risk_level": "HIGH" if api_response.get('total_hits', 0) > 0 else "LOW",
                "requires_review": api_response.get('total_hits', 0) > 0,
                "check_timestamp": check_timestamp,
                "file_title": internal_file.title,
                "filename": filename
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Http404 as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
