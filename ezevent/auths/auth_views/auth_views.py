from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status
from django.core.files.uploadedfile import InMemoryUploadedFile
import os
import uuid
from datetime import datetime
from firebase_admin import storage
import jwt
import random
import string
import os
import uuid
from datetime import datetime
from firebase_admin import storage

from django.utils.timezone import now
from django.middleware import csrf
from django.http import JsonResponse
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html
from django.core.mail import EmailMessage
from datetime import datetime, timedelta
from auths.models import Users, UserRole, Role
from admins.models import SignupToken
from auths.serializers import UserSerializer
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework import exceptions as rest_exceptions, response
from rest_framework_simplejwt import views as jwt_views, serializers as jwt_serializers, exceptions as jwt_exceptions
from rest_framework.views import APIView
from auths.permissions import IsAdminOrHasRole
from .admin_views import send_signup_token_email

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def home(request):
    return Response("App is live")

class GenerateSignupTokenView(APIView):
    permission_classes = [IsAdminOrHasRole]
    allowed_roles = ['admin']

    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        if not request.user.is_superuser:
            user_role = UserRole.objects.filter(user=request.user, role__name='admin').exists()
            if not user_role:
                return Response({'error': 'Only admins or superuser can generate tokens'}, status=status.HTTP_403_FORBIDDEN)

        email = request.data.get('email')
        role_name = request.data.get('role')

        role = Role.objects.filter(name=role_name).first()
        if not role:
            return Response({'error': 'Invalid role'}, status=status.HTTP_400_BAD_REQUEST)

        token = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(hours=24)

        signup_token = SignupToken.objects.create(
            token=token, 
            role=role,
            expires_at=expires_at, 
            used=False
        )

        try:
            send_signup_token_email(email, token, role_name)
        except Exception as e:
            return Response({'error': f'Failed to send email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'success': True, 'message': 'Signup token sent to email'}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def signup_with_token(request):
    token = request.data.get('token')
    if not token:
        return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

    signup_token = SignupToken.objects.filter(token=token).first()

    if not signup_token or not signup_token.is_valid():
        return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()

        UserRole.objects.create(user=user, role=signup_token.role)

        signup_token.used = True
        signup_token.save()

        return Response({
            'success': True,
            'message': 'User signed up successfully.'
        }, status=status.HTTP_201_CREATED)

    return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def signup_clients(request):
    serializer = UserSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()

        role_instance = get_object_or_404(Role, name="client")  
        
        UserRole.objects.create(user=user, role=role_instance)

        return Response({
            'success': True,
            'message': 'User signed up successfully.'
        }, status=status.HTTP_201_CREATED)

    return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

def get_user_tokens(user, role_name):
    refresh = RefreshToken.for_user(user)
    access_token = refresh.access_token

    access_token['role'] = role_name
    return {
        "refresh_token": str(refresh),
        "access_token": str(access_token)
    }

@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])    
def login(request):
    user = get_object_or_404(Users, email=request.data['email'])

    if user.is_suspended:
        return Response({'detail': 'Your account is suspended. Contact support.'}, status=status.HTTP_403_FORBIDDEN)
    
    if not user.check_password(request.data['password']):
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    user_role = UserRole.objects.filter(user=user).first()
    role_name = user_role.role.name if user_role else 'admin'

    tokens = get_user_tokens(user, role_name)

    serializer = UserSerializer(instance=user)

    response_data = {
        'access': tokens["access_token"],
        'user': serializer.data,
        'role': role_name
    }

    response = JsonResponse(response_data, status=status.HTTP_200_OK)

    response.set_cookie(
        key=settings.SIMPLE_JWT["AUTH_COOKIE"],
        value=tokens["access_token"],
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),  # Convert timedelta to seconds
        secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
        httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
        samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"]
    )

    response.set_cookie(
        key=settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
        value=tokens["refresh_token"],
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),  # Convert timedelta to seconds
        secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
        httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
        samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"]
    )


    csrf_token = csrf.get_token(request)
    response.set_cookie(
        key='csrftoken',
        value=csrf_token,
        secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
        httponly=False,  
        samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE']
    )

    response['X-CSRFToken'] = csrf_token

    return response

@api_view(['GET'])
def test_token(request):
   return Response(f"{request.user.email} is authenticated")

def forgot_password_token(email):
    """Generate a JWT token for password reset"""
    payload = {
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=1), 
        'iat': datetime.utcnow() 
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token

@api_view(['POST'])
@authentication_classes([])  
@permission_classes([]) 
def send_forgot_password_email(request):
    """Sends a password reset email with a token link"""
    email = request.data.get('email')

    user = Users.objects.filter(email=email).first()
    if not user:
        return Response({"error": "User with this email does not exist."}, status=400)

    token = forgot_password_token(email)

    subject = 'Forgot Password - Ezevents'
    reset_url = f"https://ez-event.vercel.app/resetPassword.html?token={token}"
    message = format_html(f"""
    <html>
    <body>
        <p>Hello {user.lastname},</p>
        
        <p>It looks like you requested a password reset. Please click the button below to reset your password:</p>
        
        <p>
            <a href="{reset_url}" 
               style="display: inline-block; padding: 10px 20px; color: white; background-color: #007BFF; 
                      text-decoration: none; border-radius: 5px;">
                Reset Password
            </a>
        </p>
        
        <p>If the button doesn't work, use this link:</p>
        
        <p><a href="{reset_url}">{reset_url}</a></p>
        
        <p>If you did not request this, please ignore this email.</p>
        
        <p>Best regards,<br>Ezevents Team</p>
    </body>
    </html>
    """)

    email_message = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
    email_message.content_subtype = 'html'
    email_message.send(fail_silently=False)

    return Response({"message": "Password reset email has been sent."}, status=200)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def update_password(request):
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        email = payload['email']
        
        user = Users.objects.filter(email=email).first()
        if user is None:
            return Response({"error": "Invalid token or user does not exist."}, status=400)
        
        user.set_password(new_password)
        user.save()
        
        return Response({"message": "Password has been reset successfully."}, status=200)
    except jwt.ExpiredSignatureError:
        return Response({"error": "Token has expired."}, status=400)
    except jwt.InvalidTokenError:
        return Response({"error": "Invalid token."}, status=400)


@api_view(['POST'])
@authentication_classes([])  
@permission_classes([])    
def logout(request):
    try:
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        
        if not refresh_token:
            raise rest_exceptions.AuthenticationFailed("Refresh token not found in cookies.")
        
        token = RefreshToken(refresh_token)
        token.blacklist()

        res = response.Response({'detail': 'Successfully logged out'}, status=status.HTTP_200_OK)

        res.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE'])
        res.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        res.delete_cookie("csrftoken")
        res.delete_cookie("X-CSRFToken")

        res["X-CSRFToken"] = None
        
        return res

    except TokenError as e:
        return response.Response({'detail': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response.Response({'detail': 'An error occurred: {}'.format(str(e))}, status=status.HTTP_400_BAD_REQUEST)
    
class CookieTokenRefreshSerializer(jwt_serializers.TokenRefreshSerializer):
    refresh = None

    def validate(self, attrs):
        attrs['refresh'] = self.context['request'].COOKIES.get('refresh')
        if attrs['refresh']:
            return super().validate(attrs)
        else:
            raise jwt_exceptions.InvalidToken(
                'No valid token found in cookie \'refresh\'')

class CookieTokenRefreshView(jwt_views.TokenRefreshView):
    serializer_class = CookieTokenRefreshSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("refresh"):
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
                value=response.data['refresh'],
                expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE']
            )

            del response.data["refresh"]
        response["X-CSRFToken"] = request.COOKIES.get("csrftoken")
        return super().finalize_response(request, response, *args, **kwargs)

class UserProfileUpdateView(generics.UpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        user = self.get_object()
        profile_pic_file = request.FILES.get('profile_pic')
        
        data = request.data.copy()
        
        if profile_pic_file:
            try:
                file_content = profile_pic_file.read()
                file_name = profile_pic_file.name
                file_ext = os.path.splitext(file_name)[1]
                
                timestamp = int(datetime.now().timestamp() * 1000)
                unique_filename = f"{timestamp}_{uuid.uuid4().hex}{file_ext}"
                
                firebase_path = f"profilePics/{unique_filename}"
                bucket = storage.bucket()
                blob = bucket.blob(firebase_path)
                
                blob.upload_from_string(
                    file_content,
                    content_type=profile_pic_file.content_type
                )
                
                blob.make_public()
                profile_pic_url = blob.public_url
                
                data['profile_pic'] = profile_pic_url
                
            except Exception as e:
                return Response(
                    {"error": f"Failed to upload profile picture: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(user, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": "success",
                "message": "Profile updated successfully",
                "user": serializer.data
            })
        
        return Response({
            "status": "error",
            "message": "Failed to update profile",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    queryset = Users.objects.all()
    lookup_field = 'id'