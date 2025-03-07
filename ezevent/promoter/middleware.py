import jwt
from django.conf import settings
from django.urls import resolve
from rest_framework.response import Response
from rest_framework import status

class ScannerTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
       
        self.protected_paths = [
            'scan_ticket',
            'scan_ticket_exit',
        ]

    def __call__(self, request):
        try:
            url_name = resolve(request.path_info).url_name
        except:
            url_name = None

        if url_name in self.protected_paths:
            token = request.GET.get('token')
            
            if not token:
                return self.token_error('Scanner token is required')
            
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                
                
                if payload.get('purpose') != 'ticket_scanning':
                    return self.token_error('Invalid token purpose')
                    
                
                request.scanner_user_id = payload.get('user_id')
                
            except jwt.ExpiredSignatureError:
                return self.token_error('Scanner token has expired')
            except jwt.InvalidTokenError:
                return self.token_error('Invalid scanner token')

        response = self.get_response(request)
        return response
    
    def token_error(self, message):
        """Helper method to return error responses"""
        from django.http import JsonResponse
        return JsonResponse({'error': message}, status=401)