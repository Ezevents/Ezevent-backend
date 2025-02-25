from rest_framework.response import Response
from django.utils import timezone
from django.core.mail import EmailMessage
from .models import  SignupToken
from auths.models import UserRole, Role, Users
from auths.serializers import UserSerializer
import random
import string
from rest_framework import status
from django.conf import settings
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from django.utils.html import format_html
from auths.permissions import IsAdminOrHasRole
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='post')
class GenerateSignupTokenView(APIView):
    permission_classes = [IsAdminOrHasRole]
    allowed_roles = ['admin']

    @csrf_exempt
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

        # Generate a 6-digit token
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

def send_signup_token_email(email, token, role_name):
    """Sending signup token via email"""
    subject = 'Your Signup Token for Ezevent'
    
    message = format_html("""
                        <html>
                        <body>
                            <p>Hello,</p>
                            
                            <p>Welcome to <strong>Ezevent</strong> – your go-to platform for seamless event planning and management!</p>
                            
                            <p>Your signup token is: <strong>{token}</strong></p>
                            
                            <p>This token is valid for 24 hours. Use it to complete your registration and start organizing successful events with ease.</p>
                            
                            <p>You can sign up as a <strong>{role_name}</strong> by clicking the button below:</p>
                            
                            <p>
                                <a href="https://billsblusters.netlify.app/public/signup.html?token={token}" 
                                style="display: inline-block; padding: 10px 20px; color: white; background-color: #007bff; 
                                        text-decoration: none; border-radius: 5px;">
                                    Complete Your Registration
                                </a>
                            </p>
                            
                            <p>If the button doesn't work, use this link:</p>
                            
                            <p><a href="https://billsblusters.netlify.app/public/signup.html?token={token}">https://billsblusters.netlify.app/public/signup.html?token={token}</a></p>
                            
                            <p>If you did not request this, please ignore this email.</p>
                            
                            <p>Best regards,<br>The Ezevent Team</p>
                        </body>
                    </html>

    """, token=token, role_name=role_name)
    
    email_message = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
    email_message.content_subtype = 'html'  
    email_message.send(fail_silently=False)

class ListPromotersView(APIView):
    permission_classes = [IsAdminOrHasRole]
    allowed_roles = ['admin']

    def get(self, request):
        promoter_role = get_object_or_404(Role, name = "promoter")
        users = Users.objects.filter(userrole__role=promoter_role).exclude(is_superuser=True)
        serializer = UserSerializer(users, many=True)
        return Response({'success': True, "data": serializer.data}, status=status.HTTP_200_OK)

class ListUsersView(APIView):
    permission_classes = [IsAdminOrHasRole]
    allowed_roles = ['admin']

    def get(self, request):
        users = Users.objects.exclude(is_superuser=True)
        serializer = UserSerializer(users, many=True)
        return Response({'success': True, "data": serializer.data}, status=status.HTTP_200_OK)

# deleting a user
class DeleteUserView(APIView):
    permission_classes = [IsAdminOrHasRole]
    allowed_roles = ['admin']

    def delete(self, request, user_id):
        user = get_object_or_404(Users, id=user_id)
        user.delete()
        return Response({'success': True, 'message': 'User deleted successfully'}, status=status.HTTP_200_OK)
    
## suspending/unsuspending a user
class SuspendUserView(APIView):
    permission_classes = [IsAdminOrHasRole]
    allowed_roles = ['admin']

    def patch(self, request, user_id):
        user = get_object_or_404(Users, id=user_id)

        user.is_suspended = not user.is_suspended
        user.save()

        status_message = "suspended" if user.is_suspended else "unsuspended"

        #notification email
        send_suspension_email(user, user.is_suspended)

        return Response({
            'success': True,
            'message': f'User has been {status_message}.'
        }, status=status.HTTP_200_OK)
    
def send_suspension_email(user, is_suspended):
    """Sending email notification about suspension/unsuspension"""
    subject = "Account Suspension Notification" if is_suspended else "Account Reactivation Notification"
    
    message = format_html("""
    <html>
    <body>
        <p>Hello {name},</p>
        
        <p>We wanted to inform you that your account has been <strong>{status_message}</strong> on our platform.</p>
        
        <p>{extra_message}</p>

        <p>If you have any questions or believe this was a mistake, please contact our support team.</p>

        <p>Best regards,<br>The Ezevent Team</p>
    </body>
    </html>
    """, name=user.firstname,
    status_message="suspended" if is_suspended else "reactivated",
    extra_message=("During suspension, you will not be able to log in or create a new account with this email." if is_suspended else 
                   "You can now log in and use your account as usual.")
    )

    email_message = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    email_message.content_subtype = 'html'  
    email_message.send(fail_silently=False)