
from datetime import datetime
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from .serializers import PurchaseSerializer
from .models import Purchase
from rest_framework.response import Response
from promoter.models import Event, TicketType
from promoter.serializers import EventSerializer, TicketTypeSerializer
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
import uuid
import qrcode
from ezevent.firebase_config import bucket
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from django.core.files.storage import default_storage
from django.http import HttpResponse
import qrcode
import os

class AvailableEventsView(generics.ListAPIView):
    """List all published events available for ticket purchase"""
    serializer_class = EventSerializer
    
    def get_queryset(self):
        return Event.objects.filter(
            status='published', 
            end_date__gt=timezone.now()
        ).order_by('start_date')

class EventTicketsView(generics.ListAPIView):
    """List all available ticket types for a specific event"""
    serializer_class = TicketTypeSerializer
    
    def get_queryset(self):
        event_id = self.kwargs.get('event_id')
        return TicketType.objects.filter(
            event_id=event_id, 
            is_active=True, 
            remaining__gt=0,
            sale_start_date__lte=timezone.now(),
            sale_end_date__gte=timezone.now()
        )

class CreatePurchaseView(generics.CreateAPIView):
    """Create a new ticket purchase"""
    serializer_class = PurchaseSerializer
    
    def create(self, request, *args, **kwargs):
        payment_screenshot = request.FILES.get('payment_screenshot')
        
        data = request.data.copy()
        
        if payment_screenshot:
            try:
                file_content = payment_screenshot.read()
                file_name = payment_screenshot.name
                file_ext = os.path.splitext(file_name)[1]

                timestamp = int(datetime.now().timestamp() * 1000)
                unique_filename = f"{timestamp}_{uuid.uuid4().hex}{file_ext}"

                firebase_path = f"payment_screenshots/{unique_filename}"
                blob = bucket.blob(firebase_path)
                
                blob.upload_from_string(
                    file_content,
                    content_type=payment_screenshot.content_type
                )
                
                blob.make_public()
                screenshot_url = blob.public_url
                
                data['payment_screenshot'] = screenshot_url
                
            except Exception as e:
                return Response(
                    {"error": f"Failed to upload payment screenshot: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if 'payment_screenshot' in data and hasattr(data['payment_screenshot'], 'read'):
            data.pop('payment_screenshot')
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        if request.user.is_authenticated:
            self.perform_create(serializer)
        else:
            serializer.save()
            
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

class InitiatePaymentView(APIView):
    """Initiate payment for a purchase"""
    def post(self, request, purchase_id):
        try:
            purchase = Purchase.objects.get(id=purchase_id)
            
            # Get payment method from request
            payment_method = request.data.get('payment_method')
            if not payment_method:
                return Response(
                    {'error': 'Payment method is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Here you would integrate with MTN/Airtel payment API
            # For now, we'll simulate payment initiation
            
            # Example implementation:
            if payment_method == 'mtn':
                # Simulate MTN payment initialization
                transaction_ref = f"MTN-{uuid.uuid4().hex[:8].upper()}"
                purchase.payment_method = 'mtn'
            elif payment_method == 'airtel':
                # Simulate Airtel payment initialization
                transaction_ref = f"AIR-{uuid.uuid4().hex[:8].upper()}"
                purchase.payment_method = 'airtel'
            else:
                return Response(
                    {'error': 'Invalid payment method'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            purchase.transaction_reference = transaction_ref
            purchase.save()
            
            # In a real implementation, you would return payment URLs or details
            return Response({
                'transaction_reference': transaction_ref,
                'payment_method': payment_method,
                'amount': purchase.total_amount,
                'payment_url': f"https://yourdomain.com/payment/confirm/{transaction_ref}/"
            })
            
        except Purchase.DoesNotExist:
            return Response(
                {'error': 'Purchase not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class SubmitPaymentProofView(generics.UpdateAPIView):
    """Client submits proof of payment"""
    serializer_class = PurchaseSerializer
    lookup_url_kwarg = 'purchase_id'
    
    def get_queryset(self):
        return Purchase.objects.all()
    
    def update(self, request, *args, **kwargs):
        purchase = self.get_object()
        
        # Handle payment screenshot upload
        if 'payment_screenshot' in request.FILES:
            purchase.payment_screenshot = request.FILES['payment_screenshot']
            purchase.save()
            return Response({
                'status': 'Payment proof submitted',
                'message': 'Your payment is awaiting approval by the event promoter'
            })
        else:
            return Response({
                'error': 'Payment screenshot is required'
            }, status=status.HTTP_400_BAD_REQUEST)


class GetPromoterContactsView(generics.RetrieveAPIView):
    """Get promoter contact details for a specific event"""
    
    def retrieve(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        
        try:
            event = Event.objects.get(id=event_id, status='published')
            promoter = event.promoter
            
            # Returning only necessary contact information
            return Response({
                'promoter_name': f"{promoter.firstname} {promoter.lastname}",
                'promoter_email': promoter.email,
                'promoter_phone': promoter.contact if hasattr(promoter, 'contact') else None,
                'payment_instructions': 'Please send the payment to the promoter and upload a screenshot of your payment receipt.'
            })
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found'
            }, status=status.HTTP_404_NOT_FOUND)

class PurchaseDetailView(generics.RetrieveAPIView):
    """Getting purchase details including QR code if approved"""
    serializer_class = PurchaseSerializer
    lookup_url_kwarg = 'purchase_id'
    
    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Purchase.objects.filter(user=self.request.user)
        else:
            email = self.request.query_params.get('email')
            if email:
                return Purchase.objects.filter(purchaser_email=email)
            return Purchase.objects.none()
        
