import os
from django.conf import settings
from django.http import HttpResponseNotFound, FileResponse

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import os
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.authentication import JWTAuthentication

from agents_loan.permissions import IsStaff
from downloadableFiles.serializers import FileUploadSerializer

# In your add_file view
if not os.path.exists(settings.DOC_DOWNLOAD_DIR):
    os.makedirs(settings.DOC_DOWNLOAD_DIR)


@extend_schema(
    summary="List all downloadable files",
    description="Retrieves a list of all files in the 'DocDownload' directory.",
    responses={200: {'type': 'array', 'items': {'type': 'string'}}, 404: {"type": "string"}},
    tags=['Files'],
)
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def list_files(request):
    try:
        files = os.listdir(settings.DOC_DOWNLOAD_DIR)
        return Response(files)
    except FileNotFoundError:
        return Response({"error": "Directory not found"}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Upload a new file",
    description="Uploads a file to the 'DocDownload' directory.",
    request=FileUploadSerializer,  # Use the serializer here
    responses={
        201: {'type': 'object', 'properties': {'filename': {'type': 'string'}}},
        400: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
    },
    tags=['Files'],
)
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated,
                     IsStaff
                     ])
def add_file(request):
    serializer = FileUploadSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    file = serializer.validated_data['file']
    file_path = os.path.join(settings.DOC_DOWNLOAD_DIR, file.name)

    with open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    return Response({"filename": file.name}, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Delete a file",
    description="Deletes the specified file from the 'DocDownload' directory.",
    responses={
        200: {'type': 'object', 'properties': {'success': {'type': 'string'}}},
        404: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
    },
    tags=['Files'],
)
@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated,
                     IsStaff
                     ])
def delete_file(request, filename):
    file_path = os.path.join(settings.DOC_DOWNLOAD_DIR, filename)
    try:
        os.remove(file_path)
        return Response({"success": f"File {filename} deleted successfully"}, status=status.HTTP_200_OK)
    except FileNotFoundError:
        return Response({"error": "File not found"}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Download a file",
    description="Downloads the specified file from the 'DocDownload' directory.",
    responses={
        200: {
            'content': {
                'application/octet-stream': {
                    'schema': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'The requested file for download.'
                    }
                }
            }
        },
        404: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
        403: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
    },
    tags=['Files'],
)
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])  # You can modify this based on your needs
def download_file(request, filename):
    # Construct the full file path
    file_path = os.path.join(settings.MEDIA_ROOT, 'DocDownload', filename)

    if not os.path.exists(file_path):
        return HttpResponseNotFound(f"The file {filename} does not exist.")

    # Here you can add any permission checks to ensure the user can access the file
    # For example, you could check if the user is allowed to download this file
    # if not request.user.has_permission(...):
    #     return HttpResponseForbidden("You do not have permission to download this file.")

    # Serve the file
    response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    return response
