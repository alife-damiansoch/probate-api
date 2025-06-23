from datetime import datetime

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import LoanBook
from .serializers import LoanBookSerializer
from loan.permissions import IsStaff
from django.utils import timezone
from rest_framework.response import Response


class LoanBookDetailView(generics.RetrieveAPIView):
    queryset = LoanBook.objects.all()
    serializer_class = LoanBookSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        date_str = request.query_params.get('date')
        on_date = timezone.now().date()
        if date_str:
            try:
                on_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        data = self.get_serializer(instance).data
        data["statement"] = instance.generate_statement(on_date)
        return Response(data)
