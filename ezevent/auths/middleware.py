import jwt
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.conf import settings
from .models import Users, UserRole
from django.urls import resolve

class JWTAuthenticationMiddleware(MiddlewareMixin):
    EXEMPT_URLS = [
        '/api/token/refresh/',
        '/token/',
        '/api/refresh/',
        '/auth/logout',
        '/auth/login',
        '/auth/signup',
        '/auth/token_signup',
        '/public/auth/refresh-token',
        '/admin/',
        '/auth/active',
        '/update_profile_picture',
        '/auth/forgotPassword', 
        '/auth/updatepassword',
        '/api/google-oauth2/login/raw/redirect/',
        '/api/google-oauth2/login/raw/callback/',
        '/auth/update_profile'
    ]

    ADMIN_URL_PREFIX = '/admin/'

    def process_request(self, request):
        path = request.path

        if any(path.startswith(url) for url in self.EXEMPT_URLS):
            return None

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Unauthorized access'}, status=401)

        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user = Users.objects.get(id=payload['user_id'])
            request.user = user
            request.user_role = payload.get('role', None)

            if path.startswith(self.ADMIN_URL_PREFIX) and not (
                user.is_superuser or self.user_has_admin_role(user)
            ):
                return JsonResponse({'error': 'Forbidden: Admin access only'}, status=403)
        
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Users.DoesNotExist) as e:
            print(f"Authentication error: {str(e)}")
            return JsonResponse({'error': 'Unauthorized access'}, status=401)
        
    def user_has_admin_role(self, user):
        try:
            user_role = UserRole.objects.get(user=user)  
            return user_role.role.name == 'admin'
        except UserRole.DoesNotExist:
            return False
        
class CustomCSRFMiddleware(MiddlewareMixin):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        try:
            resolved = resolve(request.path_info)
            print(f"Processing view: {resolved.func.__name__}")  
            print(f"Full path: {resolved.view_name}")          
            print(f"URL pattern: {resolved.url_name}")          
        except Exception as e:
            print(f"Resolution error: {e}")

        exempt_views = [
            'admins.views.GenerateSignupTokenView',
            'auths.auth_views.auth_views.login',
            # 'auth.views.signup_normal_user',
            # 'auth.views.signup_with_token',
            'auths.views.CookieTokenRefreshView'
        ]
        
        if request.path_info.startswith('/admin/generate_signup_token'): 
            request.csrf_processing_done = True
            return None

        return None
    
    