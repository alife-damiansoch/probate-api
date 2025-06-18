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
