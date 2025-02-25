
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

class PromoterPaymentApprovalView(generics.UpdateAPIView):
    """Promoter approves payment and generates PDF ticket with QR code"""
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'purchase_id'
    
    def get_queryset(self):
        # Only allow promoters to approve payments for their events
        return Purchase.objects.filter(ticket_type__event__promoter=self.request.user)
    
    def update(self, request, *args, **kwargs):
        purchase = self.get_object()
        approve = request.data.get('approve', False)
        
        if not approve:
            return Response({
                'status': 'Payment not approved',
                'message': 'You have chosen not to approve this payment'
            })
        
        # Approve payment
        purchase.is_approved_by_promoter = True
        purchase.payment_status = 'completed'
        purchase.approval_date = timezone.now()
        
        # Generate QR code
        qr_data = {
            'purchase_id': purchase.id,
            'event': purchase.ticket_type.event.title,
            'ticket_type': purchase.ticket_type.name,
            'quantity': purchase.quantity,
            'purchaser': purchase.purchaser_email,
            'approved_by': self.request.user.username,
            'approval_date': purchase.approval_date.isoformat()
        }
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(str(qr_data))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Saving QR code temporarily
        temp_qr_path = f'temp_qr_{purchase.id}.png'
        img.save(temp_qr_path)
        
        # Creating PDF ticket
        pdf_filename = f'ticket_{purchase.id}.pdf'
        pdf_path = f'tickets/{pdf_filename}'
        
        # Generating PDF
        c = canvas.Canvas(pdf_path, pagesize=letter)
        
        # Adding event details
        event = purchase.ticket_type.event
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(letter[0]/2, 10*inch, event.title)
        
        c.setFont("Helvetica", 14)
        c.drawCentredString(letter[0]/2, 9.5*inch, f"Date: {event.start_date.strftime('%B %d, %Y')}")
        c.drawCentredString(letter[0]/2, 9.2*inch, f"Time: {event.start_date.strftime('%I:%M %p')} - {event.end_date.strftime('%I:%M %p')}")
        c.drawCentredString(letter[0]/2, 8.9*inch, f"Location: {event.location}")
        
        # Adding ticket information
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(letter[0]/2, 8*inch, f"Ticket: {purchase.ticket_type.name}")
        
        c.setFont("Helvetica", 12)
        c.drawCentredString(letter[0]/2, 7.7*inch, f"Quantity: {purchase.quantity}")
        c.drawCentredString(letter[0]/2, 7.4*inch, f"Purchaser: {purchase.purchaser_email}")
        c.drawCentredString(letter[0]/2, 7.1*inch, f"Purchase Date: {purchase.purchase_date.strftime('%B %d, %Y')}")
        
        # Adding attendee information if available
        attendees = PurchaseAttendee.objects.filter(purchase=purchase)
        if attendees.exists():
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(letter[0]/2, 6.3*inch, "Attendees:")
            
            c.setFont("Helvetica", 12)
            y_position = 6*inch
            for i, purchase_attendee in enumerate(attendees):
                attendee = purchase_attendee.attendee
                c.drawCentredString(letter[0]/2, y_position, f"{i+1}. {attendee.first_name} {attendee.last_name}")
                y_position -= 0.3*inch
        
        # Adding QR code
        c.drawImage(temp_qr_path, letter[0]/2 - 1.5*inch, 3*inch, width=3*inch, height=3*inch)
        
        c.setFont("Helvetica", 10)
        c.drawCentredString(letter[0]/2, 2.5*inch, "Please present this QR code at the event entrance")
        
        # Adding footer
        c.setFont("Helvetica-Italic", 8)
        c.drawCentredString(letter[0]/2, 1*inch, "This ticket is valid only for the named event and date.")
        c.drawCentredString(letter[0]/2, 0.8*inch, f"Ticket ID: {purchase.id}")
        
        c.save()
        
        # Cleaning up temporary file
        os.remove(temp_qr_path)
        
        # Saving PDF path to model
        with open(pdf_path, 'rb') as f:
            purchase.ticket_pdf = ContentFile(f.read(), name=pdf_filename)
        
        purchase.save()
        
        # Removing the local copy
        os.remove(pdf_path)
        
        return Response({
            'status': 'Payment approved',
            'message': 'PDF ticket has been generated and is available for the customer',
            'ticket_pdf_url': purchase.ticket_pdf.url
        })

class GetPromoterContactsView(generics.RetrieveAPIView):
    """Get promoter contact details for a specific event"""
    
    def retrieve(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        
        try:
            event = Event.objects.get(id=event_id, status='published')
            promoter = event.promoter
            
            # Returning only necessary contact information
            return Response({
                'promoter_name': f"{promoter.first_name} {promoter.last_name}",
                'promoter_email': promoter.email,
                'promoter_phone': promoter.phone if hasattr(promoter, 'phone') else None,
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