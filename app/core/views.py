from django.http import HttpResponseServerError


def test_500_view(request):
    # This will cause a server error
    return HttpResponseServerError()
