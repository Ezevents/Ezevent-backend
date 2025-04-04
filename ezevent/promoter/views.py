from rest_framework.exceptions import NotFound
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Event, TicketType
from .serializers import EventSerializer, TicketTypeSerializer
from django.db.models import Q, Count, Sum, F
from django.db.models.functions import TruncMonth, TruncDay
from rest_framework.views import APIView
from datetime import datetime, timedelta
from django.conf import settings
from django.core.files.base import ContentFile
from client.models import Purchase, TicketPDF
from client.serializers import PurchaseSerializer
from django.utils import timezone
import jwt
import ast
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import qrcode
import os
import uuid
from io import BytesIO
from ezevent.firebase_config import bucket
from django.core.mail import EmailMessage
from django.utils.html import format_html
import requests
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils import timezone
import tempfile
from io import BytesIO

import logging
logger = logging.getLogger(__name__)
class CreateEventView(generics.CreateAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        event_image = request.FILES.get('image')
        
        data = request.data.copy()
        
        if event_image:
            try:
                file_content = event_image.read()
                file_name = event_image.name
                file_ext = os.path.splitext(file_name)[1]

                timestamp = int(datetime.now().timestamp() * 1000)
                unique_filename = f"{timestamp}_{uuid.uuid4().hex}{file_ext}"

                firebase_path = f"event_images/{unique_filename}"
                blob = bucket.blob(firebase_path)
                
                blob.upload_from_string(
                    file_content,
                    content_type=event_image.content_type
                )
                
                blob.make_public()
                image_url = blob.public_url
                
                data['profile_pic'] = image_url
                
                if 'image' in data:
                    data.pop('image')
                
            except Exception as e:
                return Response(
                    {"error": f"Failed to upload event image: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(promoter=self.request.user)

class ListEventsView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Event.objects.filter(promoter=self.request.user)

class EventDetailView(generics.RetrieveAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'event_id'

    def get_queryset(self):
        return Event.objects.filter(promoter=self.request.user)

class UpdateEventView(generics.UpdateAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'event_id'

    def get_queryset(self):
        return Event.objects.filter(promoter=self.request.user)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        event_image = request.FILES.get('image')
        
        data = request.data.copy()
        
        if event_image:
            try:
                file_content = event_image.read()
                file_name = event_image.name
                file_ext = os.path.splitext(file_name)[1]

                timestamp = int(datetime.now().timestamp() * 1000)
                unique_filename = f"{timestamp}_{uuid.uuid4().hex}{file_ext}"

                firebase_path = f"event_images/{unique_filename}"
                blob = bucket.blob(firebase_path)
                
                blob.upload_from_string(
                    file_content,
                    content_type=event_image.content_type
                )
                
                blob.make_public()
                image_url = blob.public_url
                
                data['profile_pic'] = image_url

                if 'image' in data:
                    data.pop('image')
                
            except Exception as e:
                return Response(
                    {"error": f"Failed to upload event image: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)
    
class PublishEventView(APIView):
    """Publish an event that's currently in draft status"""
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, event_id):
        try:
            #getting the event and verify ownership
            event = Event.objects.get(id=event_id, promoter=request.user)
            
            #checking if it's in draft status
            if event.status != 'draft':
                return Response({
                    'error': 'Only draft events can be published',
                    'current_status': event.status
                }, status=status.HTTP_400_BAD_REQUEST)
            
            #updating status to published
            event.status = 'published'
            event.save()
            
            serializer = EventSerializer(event)
            
            return Response({
                'status': 'success',
                'message': f'Event "{event.title}" has been published',
                'event': serializer.data
            })
            
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found or you do not have permission to publish it'
            }, status=status.HTTP_404_NOT_FOUND)

class DeleteEventView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'event_id'

    def get_queryset(self):
        return Event.objects.filter(promoter=self.request.user)


class CreateTicketView(generics.CreateAPIView):
    serializer_class = TicketTypeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        event_id = self.kwargs.get('event_id')
        try:
            event = Event.objects.get(id=event_id, promoter=self.request.user)
            serializer.save(event=event)
        except Event.DoesNotExist:
            raise NotFound("Event not found or you don't have permission to add tickets to this event")

class ListTicketsView(generics.ListAPIView):
    serializer_class = TicketTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TicketType.objects.filter(
            event_id=self.kwargs['event_id'],
            event__promoter=self.request.user
        )

class UpdateTicketView(generics.UpdateAPIView):
    serializer_class = TicketTypeSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'ticket_id'

    def get_queryset(self):
        return TicketType.objects.filter(event__promoter=self.request.user)

class DeleteTicketView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'ticket_id'

    def get_queryset(self):
        return TicketType.objects.filter(event__promoter=self.request.user)

class EventSummaryView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id, promoter=request.user)
            ticket_types = event.ticket_types.all()
            
            summary = {
                'event_name': event.title,
                'total_tickets': sum(tt.quantity for tt in ticket_types),
                'tickets_sold': sum(tt.quantity - tt.remaining for tt in ticket_types),
                'revenue': sum((tt.quantity - tt.remaining) * tt.price for tt in ticket_types),
                'ticket_types': [{
                    'name': tt.name,
                    'sold': tt.quantity - tt.remaining,
                    'remaining': tt.remaining,
                    'revenue': (tt.quantity - tt.remaining) * tt.price
                } for tt in ticket_types]
            }
            
            return Response(summary, status=status.HTTP_200_OK)
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class SearchEventsView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Event.objects.filter(promoter=self.request.user)
        
        # Search parameters
        search_term = self.request.query_params.get('search', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        status = self.request.query_params.get('status', None)
        category = self.request.query_params.get('category', None)
        
        if search_term:
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term) |
                Q(location__icontains=search_term)
            )
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
        
        if status:
            queryset = queryset.filter(status=status)
            
        if category:
            queryset = queryset.filter(category=category)
            
        return queryset

class BulkCreateTicketsView(generics.CreateAPIView):
    serializer_class = TicketTypeSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id, promoter=request.user)
            tickets_data = request.data.get('tickets', [])
            
            created_tickets = []
            errors = []

            for ticket_data in tickets_data:
                ticket_data['event'] = event.id
                serializer = self.get_serializer(data=ticket_data)
                
                if serializer.is_valid():
                    ticket = serializer.save()
                    created_tickets.append(serializer.data)
                else:
                    errors.append({
                        'ticket_name': ticket_data.get('name'),
                        'errors': serializer.errors
                    })

            response_data = {
                'created_tickets': created_tickets,
                'errors': errors
            }

            if errors:
                return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class EventAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get date range from query params or default to last 30 days
        end_date = datetime.now()
        start_date = self.request.query_params.get(
            'start_date', 
            (end_date - timedelta(days=30)).strftime('%Y-%m-%d')
        )
        
        events = Event.objects.filter(
            promoter=request.user,
            start_date__gte=start_date
        )

        analytics = {
            'total_events': events.count(),
            'upcoming_events': events.filter(start_date__gt=datetime.now()).count(),
            'total_revenue': events.annotate(
                revenue=Sum(F('ticket_types__quantity') - F('ticket_types__remaining')) * 
                       F('ticket_types__price')
            ).aggregate(total=Sum('revenue'))['total'] or 0,
            
            'tickets_sold': events.annotate(
                sold=Sum(F('ticket_types__quantity') - F('ticket_types__remaining'))
            ).aggregate(total=Sum('sold'))['total'] or 0,
            
            'monthly_events': events.annotate(
                month=TruncMonth('start_date')
            ).values('month').annotate(
                count=Count('id')
            ).order_by('month'),
            
            'events_by_category': events.values('category').annotate(
                count=Count('id')
            ).order_by('-count'),
            
            'popular_venues': events.values('venue').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        }
        
        return Response(analytics)

class SingleEventAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id, promoter=request.user)
            ticket_types = event.ticket_types.all()

            daily_sales = TicketType.objects.filter(
                event=event
            ).annotate(
                day=TruncDay('created_at')
            ).values('day').annotate(
                sales=Count('id')
            ).order_by('day')

            analytics = {
                'event_details': {
                    'title': event.title,
                    'start_date': event.start_date,
                    'status': event.status
                },
                'ticket_summary': {
                    'total_tickets': sum(tt.quantity for tt in ticket_types),
                    'tickets_sold': sum(tt.quantity - tt.remaining for tt in ticket_types),
                    'revenue': sum((tt.quantity - tt.remaining) * tt.price for tt in ticket_types)
                },
                'ticket_types_breakdown': [{
                    'name': tt.name,
                    'total': tt.quantity,
                    'sold': tt.quantity - tt.remaining,
                    'revenue': (tt.quantity - tt.remaining) * tt.price,
                    'percentage_sold': ((tt.quantity - tt.remaining) / tt.quantity) * 100 if tt.quantity > 0 else 0
                } for tt in ticket_types],
                'daily_sales': daily_sales
            }

            return Response(analytics, status=status.HTTP_200_OK)

        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class PendingPaymentsListView(generics.ListAPIView):
    """List all purchases with pending payments for the promoter's events"""
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        events = Event.objects.filter(promoter=self.request.user)
        
        return Purchase.objects.filter(
            ticket_type__event__in=events,
            payment_status='pending',
            payment_screenshot__isnull=False,  
            is_approved_by_promoter=False
        ).order_by('-purchase_date').select_related('ticket_type', 'ticket_type__event')
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        event_id = request.query_params.get('event_id')
        if event_id:
            queryset = queryset.filter(ticket_type__event_id=event_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class PromoterPaymentApprovalView(generics.UpdateAPIView):
    """Promoter approves payment and generates PDF ticket with QR code"""
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'purchase_id'
    
    def get_queryset(self):
        return Purchase.objects.filter(ticket_type__event__promoter=self.request.user)
    
    def update(self, request, *args, **kwargs):
        purchase = self.get_object()
        approve = request.data.get('approve', False)
        
        if not approve:
            return Response({
                'status': 'Payment not approved',
                'message': 'You have chosen not to approve this payment'
            })
        
        # Approving payment
        purchase.is_approved_by_promoter = True
        purchase.payment_status = 'completed'
        purchase.approval_date = timezone.now()
        purchase.save()
        
        # Creating a temp directory for QR codes
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Get attendees or create a default one if none exist
        from client.models import PurchaseAttendee, Attendee
        purchase_attendees = PurchaseAttendee.objects.filter(purchase=purchase)
        
        if not purchase_attendees.exists():
            # If no attendees were specified, create a default one using purchaser info
            default_attendee = Attendee.objects.create(
                first_name="Guest",
                last_name="Attendee",
                email=purchase.purchaser_email,
                phone=purchase.purchaser_phone
            )
            purchase_attendee = PurchaseAttendee.objects.create(
                purchase=purchase,
                attendee=default_attendee
            )
            purchase_attendees = [purchase_attendee]
        
        # Storing all generated PDFs and their info
        ticket_pdfs = []
        
        # Generating a PDF for each attendee
        for idx, purchase_attendee in enumerate(purchase_attendees):
            attendee = purchase_attendee.attendee
            
            # Generating QR code with attendee-specific info
            qr_data = {
                'purchase_id': purchase.id,
                'event': purchase.ticket_type.event.title,
                'ticket_type': purchase.ticket_type.name,
                'attendee_id': attendee.id,
                'attendee_name': f"{attendee.first_name} {attendee.last_name}",
                'attendee_email': attendee.email,
                'approved_by': self.request.user.get_full_name(),
                'approval_date': purchase.approval_date.isoformat(),
                'used': False  
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
            
            # Saving QR code to temp directory
            temp_qr_path = os.path.join(temp_dir, f'temp_qr_{purchase.id}_{attendee.id}.png')
            img.save(temp_qr_path)
            
            # Generating PDF filename
            pdf_filename = f'ticket_{purchase.id}_{attendee.id}.pdf'
            
            # Generating PDF in memory
            pdf_buffer = BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=letter)

            c.setFont("Helvetica-Bold", 24)
            c.drawCentredString(letter[0]/2, 10*inch, purchase.ticket_type.event.title)

            c.setFont("Helvetica", 14)
            c.drawCentredString(letter[0]/2, 9.5*inch, f"Date: {purchase.ticket_type.event.start_date.strftime('%B %d, %Y')}")
            c.drawCentredString(letter[0]/2, 9.2*inch, f"Time: {purchase.ticket_type.event.start_date.strftime('%I:%M %p')} - {purchase.ticket_type.event.end_date.strftime('%I:%M %p')}")
            c.drawCentredString(letter[0]/2, 8.9*inch, f"Location: {purchase.ticket_type.event.location}")

            # Adding ticket information
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(letter[0]/2, 8*inch, f"Ticket: {purchase.ticket_type.name}")

            c.setFont("Helvetica", 12)
            c.drawCentredString(letter[0]/2, 7.5*inch, f"Purchase Date: {purchase.purchase_date.strftime('%B %d, %Y')}")

            c.drawImage(temp_qr_path, letter[0]/2 - 2*inch, 3.5*inch, width=4*inch, height=4*inch)

            c.setFont("Helvetica", 10)
            c.drawCentredString(letter[0]/2, 2.5*inch, "Please present this QR code at the event entrance")

            c.setFont("Helvetica", 8)
            c.drawCentredString(letter[0]/2, 1*inch, "This ticket is valid only for the named event and date.")
            c.drawCentredString(letter[0]/2, 0.8*inch, f"This ticket is for one person only and is non-transferable.")

            c.save()
            
            pdf_buffer.seek(0)
            pdf_content = pdf_buffer.getvalue()
            
            # Uploading to Firebase Storage
            firebase_path = f'tickets/{pdf_filename}'
            blob = bucket.blob(firebase_path)
            blob.upload_from_string(pdf_content, content_type='application/pdf')
            
            # Making the file publicly accessible
            blob.make_public()
            pdf_url = blob.public_url
            
            ticket_info = {
                'attendee_id': attendee.id,
                'attendee_name': f"{attendee.first_name} {attendee.last_name}",
                'attendee_email': attendee.email,
                'filename': pdf_filename,
                'firebase_url': pdf_url
            }
            ticket_pdfs.append(ticket_info)
            
            # Cleaning up QR code temp file
            try:
                os.remove(temp_qr_path)
            except:
                pass
        
        for idx, ticket_info in enumerate(ticket_pdfs):
            TicketPDF.objects.create(
                purchase_id=purchase.id,
                attendee_id=ticket_info['attendee_id'],
                pdf_url=ticket_info['firebase_url'],
                is_used=False
            )
            
            if idx == 0: 
                purchase.ticket_pdf_url = ticket_info['firebase_url']
                purchase.save()
        
        # Preparing response with all ticket URLs
        response_data = {
            'status': 'Payment approved',
            'message': f'PDF tickets have been generated for {len(ticket_pdfs)} attendees',
            'ticket_pdf_url': purchase.ticket_pdf_url,
            'attendees': []
        }
        
        for ticket_info in ticket_pdfs:
            response_data['attendees'].append({
                'name': ticket_info['attendee_name'],
                'email': ticket_info['attendee_email'],
                'ticket_url': ticket_info['firebase_url']
            })

        send_payment_approval_email(purchase, ticket_pdfs)

        return Response(response_data)


def send_payment_approval_email(purchase, ticket_pdfs):
    event = purchase.ticket_type.event
    subject = f'Payment Approved for {event.title}'
    
    attendee_tickets_html = ""
    for ticket_info in ticket_pdfs:
        attendee_tickets_html += format_html("""
            <p><strong>{name}:</strong> <a href="{ticket_url}" 
            style="display: inline-block; padding: 10px 20px; color: white; background-color: #007bff; 
            text-decoration: none; border-radius: 5px;">Download Ticket</a></p>
        """, name=ticket_info['attendee_name'], ticket_url=ticket_info['firebase_url'])
    
    message = format_html("""
        <html>
        <body>
            <p>Hello {customer_name},</p>
            
            <p>Great news! Your payment for <strong>{event_title}</strong> has been approved. Your tickets are now ready.</p>
            
            <h2>Event Details</h2>
            <p><strong>Event:</strong> {event_title}</p>
            <p><strong>Date:</strong> {event_date}</p>
            <p><strong>Time:</strong> {event_time}</p>
            <p><strong>Location:</strong> {event_location}</p>
            <p><strong>Ticket Type:</strong> {ticket_type}</p>
            <p><strong>Number of Tickets:</strong> {ticket_count}</p>
            
            <h2>Your Tickets</h2>
                          
            <p>You can access your tickets in the attachments section below</p>
            
            <p>Please present these tickets (either printed or on your mobile device) at the event entrance.</p>
            
            <p>Thank you for your purchase. We look forward to seeing you at the event!</p>
            <p>If you have any questions, please contact our support team.</p>
            
            <p>Best regards,<br>The Ezevent Team</p>
        </body>
        </html>
    """, 
    customer_name=purchase.purchaser_name if hasattr(purchase, 'purchaser_name') else "Customer",
    event_title=event.title,
    event_date=event.start_date.strftime('%B %d, %Y'),
    event_time=f"{event.start_date.strftime('%I:%M %p')} - {event.end_date.strftime('%I:%M %p')}",
    event_location=event.location,
    ticket_type=purchase.ticket_type.name,
    ticket_count=len(ticket_pdfs),
    attendee_tickets=attendee_tickets_html)
    
    email_message = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [purchase.purchaser_email])
    email_message.content_subtype = 'html'
    
    # Attaching PDF tickets to the email
    for ticket_info in ticket_pdfs:
        pdf_response = requests.get(ticket_info['firebase_url'])
        if pdf_response.status_code == 200:
            filename = f"Ticket - {event.title} - {ticket_info['attendee_name']}.pdf"
            email_message.attach(filename, pdf_response.content, 'application/pdf')
    
    email_message.send(fail_silently=False)

def generate_scanner_url(user_id, expiry_hours=24):
    """Generating a JWT-secured URL for ticket scanning that expires after specified hours"""
    import datetime
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=expiry_hours),
        'iat': datetime.datetime.utcnow(),
        'purpose': 'ticket_scanning'
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    # Frontend URLs
    entry_url = f"https://ez-event.vercel.app/scan?token={token}"
    exit_url = f"https://ez-event.vercel.app/scan-exit?token={token}"
    injury_exit_url = f"https://ez-event.vercel.app/scan-exit?token={token}&mode=injury"
    
    return {
        'entry_url': entry_url,
        'exit_url': exit_url,
        'injury_exit_url': injury_exit_url,
        'expires_at': payload['exp']
    }

class GenerateScannerUrlView(APIView):
    permission_classes = [IsAuthenticated]  
    
    def post(self, request):
        user_id = request.user.id
        
        urls = generate_scanner_url(user_id)
        return Response(urls)

class ScanTicketView(APIView):
    """Scanning and validating a ticket""" 
    permission_classes = []  
    authentication_classes = []
    
    def post(self, request, format=None):
        scanner_id = getattr(request, 'scanner_user_id', None)
        try:
            # Getting the QR data from the request
            qr_data = request.data.get('qr_data')
            if not qr_data:
                return Response({'error': 'QR data is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            ticket_info = ast.literal_eval(qr_data)
            
            # Extracting ticket information
            purchase_id = ticket_info.get('purchase_id')
            attendee_id = ticket_info.get('attendee_id')
            
            # Finding the ticket - using filter instead of get to handle potential duplicates
            tickets = TicketPDF.objects.filter(
                purchase_id=purchase_id,
                attendee_id=attendee_id
            )
            
            if not tickets.exists():
                return Response({
                    'valid': False,
                    'error': 'Ticket not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Use the first ticket if multiple exist
            if tickets.count() > 1:
                # Log this issue for investigation
                logger.warning(f"Duplicate tickets found: {purchase_id}, {attendee_id}")
                
            ticket = tickets.first()
            
            # Checking if ticket is already used
            if ticket.is_used:
                return Response({
                    'valid': False,
                    'error': 'Ticket has already been used',
                    'used_at': ticket.used_at
                })
            
            # Checking if the event is still valid
            event = ticket.purchase.ticket_type.event
            if event.end_date < timezone.now():
                return Response({
                    'valid': False,
                    'error': 'Event has already ended'
                })
            
            # Marking ticket as used
            ticket.scanned_by = scanner_id
            ticket.is_used = True
            ticket.used_at = timezone.now()
            ticket.save()
            
            # Returning success response
            return Response({
                'valid': True,
                'attendee': {
                    'name': f"{ticket.attendee.first_name} {ticket.attendee.last_name}",
                    'email': ticket.attendee.email
                },
                'event': {
                    'title': event.title,
                    'location': event.location,
                    'start_date': event.start_date
                },
                'ticket_type': ticket.purchase.ticket_type.name,
                'scanned_at': ticket.used_at
            })
            
        except Exception as e:
            return Response({
                'valid': False,
                'error': f'Invalid QR code data: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

class ScanTicketExitView(APIView):
    """Scanning and validating a ticket for exit"""
    permission_classes = []  
    authentication_classes = []
    
    def post(self, request, format=None):
        scanner_id = getattr(request, 'scanner_user_id', None)
        try:
            qr_data = request.data.get('qr_data')
            exit_reason = request.data.get('exit_reason', 'normal') 
            injury_notes = request.data.get('injury_notes', '')      
            
            if not qr_data:
                return Response({'error': 'QR data is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            ticket_info = ast.literal_eval(qr_data)
            
            purchase_id = ticket_info.get('purchase_id')
            attendee_id = ticket_info.get('attendee_id')
            
            tickets = TicketPDF.objects.filter(
                purchase_id=purchase_id,
                attendee_id=attendee_id
            )
            
            if not tickets.exists():
                return Response({
                    'valid': False,
                    'error': 'Ticket not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            if tickets.count() > 1:
                logger.warning(f"Duplicate tickets found for exit: {purchase_id}, {attendee_id}")
                
            ticket = tickets.first()
            
            if not ticket.is_used:
                return Response({
                    'valid': False,
                    'error': 'Ticket has not been used for entry yet'
                })
            
            if ticket.exit_time:
                return Response({
                    'valid': False,
                    'error': 'Ticket has already been used for exit',
                    'exit_time': ticket.exit_time,
                    'exit_reason': ticket.exit_reason
                })
        
            event = ticket.purchase.ticket_type.event
            if event.end_date < timezone.now():
                logger.info(f"Exit after event end for ticket: {purchase_id}, {attendee_id}")
        
            ticket.exit_scanned_by = scanner_id
            ticket.exit_time = timezone.now()
            ticket.exit_reason = exit_reason 
            ticket.injury_notes = injury_notes 
            
            ticket.time_spent = ticket.exit_time - ticket.used_at
            ticket.save()
            
            hours, remainder = divmod(ticket.time_spent.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_spent_str = f"{int(hours)}h {int(minutes)}m"
            
            if exit_reason == 'injured' or exit_reason == 'emergency':
                logger.warning(f"MEDICAL ATTENTION NEEDED: Attendee {ticket.attendee.first_name} {ticket.attendee.last_name} exited with status '{exit_reason}'")
            
            return Response({
                'valid': True,
                'attendee': {
                    'name': f"{ticket.attendee.first_name} {ticket.attendee.last_name}",
                    'email': ticket.attendee.email
                },
                'event': {
                    'title': event.title,
                    'location': event.location,
                    'start_date': event.start_date
                },
                'ticket_type': ticket.purchase.ticket_type.name,
                'entry_time': ticket.used_at,
                'exit_time': ticket.exit_time,
                'exit_reason': ticket.exit_reason,
                'time_spent': time_spent_str
            })
            
        except Exception as e:
            return Response({
                'valid': False,
                'error': f'Invalid QR code data: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
class TicketDetailsView(APIView):
    """View to get ticket details including entry/exit times"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, ticket_id=None, format=None):
        user_id = request.user.id
        
        try:
            promoter_events = Event.objects.filter(promoter_id=user_id).values_list('id', flat=True)
            
            if ticket_id:
                ticket = TicketPDF.objects.get(
                    id=ticket_id,
                    purchase__ticket_type__event_id__in=promoter_events
                )
                return Response(self._format_ticket_data(ticket))
            else:
                event_id = request.query_params.get('event_id')
                
                tickets = TicketPDF.objects.filter(
                    purchase__ticket_type__event_id__in=promoter_events
                )
                
                if event_id:
                    if int(event_id) not in promoter_events:
                        return Response(
                            {'error': 'You do not have permission to view tickets for this event'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    tickets = tickets.filter(purchase__ticket_type__event_id=event_id)
                
                result = [self._format_ticket_data(ticket) for ticket in tickets]
                return Response(result)
                
        except TicketPDF.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Error retrieving ticket data: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _format_ticket_data(self, ticket):
        duration = None
        duration_str = "N/A"
        
        if ticket.is_used and ticket.exit_time:
            duration = ticket.exit_time - ticket.used_at
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{int(hours)}h {int(minutes)}m"
        
        event = ticket.purchase.ticket_type.event
        
        return {
            'ticket_id': ticket.id,
            'attendee': {
                'id': ticket.attendee.id,
                'name': f"{ticket.attendee.first_name} {ticket.attendee.last_name}",
                'email': ticket.attendee.email
            },
            'event': {
                'id': event.id,
                'title': event.title
            },
            'ticket_type': ticket.purchase.ticket_type.name,
            'entry_time': ticket.used_at,
            'exit_time': ticket.exit_time,
            'duration': duration_str,
            'status': 'Completed' if ticket.exit_time else ('Still Inside' if ticket.is_used else 'Not Used')
        }
    
class InjuryReportsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, event_id=None):
        user_id = request.user.id

        if event_id:
            events = Event.objects.filter(id=event_id, promoter_id=user_id)
            if not events.exists():
                return Response({'error': 'Event not found or you do not have permission'}, 
                               status=status.HTTP_404_NOT_FOUND)
        else:
            events = Event.objects.filter(promoter_id=user_id)
        
        injury_data = []
        
        for event in events:
            ticket_types = TicketType.objects.filter(event=event)
            
            purchases = Purchase.objects.filter(ticket_type__in=ticket_types)
            
            injured_tickets = TicketPDF.objects.filter(
                purchase__in=purchases,
                exit_reason__in=['injured', 'emergency']
            )
            
            for ticket in injured_tickets:
                injury_data.append({
                    'event': event.title,
                    'attendee_name': f"{ticket.attendee.first_name} {ticket.attendee.last_name}",
                    'attendee_email': ticket.attendee.email,
                    'attendee_phone': ticket.attendee.phone,
                    'entry_time': ticket.used_at,
                    'exit_time': ticket.exit_time,
                    'exit_reason': ticket.exit_reason,
                    'injury_notes': ticket.injury_notes,
                    'ticket_type': ticket.purchase.ticket_type.name
                })
        
        return Response(injury_data)
    

class EventReportPDFView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, event_id, format=None):
        try:
            user_id = request.user.id
            try:
                event = Event.objects.get(id=event_id, promoter_id=user_id)
            except Event.DoesNotExist:
                return Response(
                    {'error': 'Event not found or you do not have permission'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            report_format = request.query_params.get('format', 'pdf')
            
            ticket_types = TicketType.objects.filter(event=event)
            purchases = Purchase.objects.filter(ticket_type__in=ticket_types)
            tickets = TicketPDF.objects.filter(purchase__in=purchases)

            stats = {
                'total_tickets_sold': purchases.aggregate(Sum('quantity'))['quantity__sum'] or 0,
                'total_revenue': purchases.filter(payment_status='completed').aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
                'total_attendees': tickets.count(),
                'attended_count': tickets.filter(is_used=True).count(),
                'normal_exits': tickets.filter(is_used=True, exit_time__isnull=False, exit_reason='normal').count(),
                'injured_exits': tickets.filter(is_used=True, exit_time__isnull=False, exit_reason__in=['injured', 'emergency']).count(),
                'still_inside': tickets.filter(is_used=True, exit_time__isnull=True).count(),
                'unused_tickets': tickets.filter(is_used=False).count(),
            }
            
            ticket_type_stats = []
            for tt in ticket_types:
                type_purchases = purchases.filter(ticket_type=tt)
                ticket_type_stats.append({
                    'name': tt.name,
                    'price': float(tt.price),
                    'sold': type_purchases.aggregate(Sum('quantity'))['quantity__sum'] or 0,
                    'revenue': float(type_purchases.filter(payment_status='completed').aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
                })
            
            injured_attendees = tickets.filter(
                is_used=True, 
                exit_time__isnull=False, 
                exit_reason__in=['injured', 'emergency']
            ).select_related('attendee')
            
            injured_list = [{
                'name': f"{ticket.attendee.first_name} {ticket.attendee.last_name}",
                'email': ticket.attendee.email,
                'phone': ticket.attendee.phone,
                'exit_time': ticket.exit_time,
                'exit_reason': ticket.exit_reason,
                'notes': ticket.injury_notes or 'No notes provided'
            } for ticket in injured_attendees]
            
            context = {
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'venue': event.venue,
                    'location': event.location,
                    'start_date': event.start_date,
                    'end_date': event.end_date,
                },
                'stats': stats,
                'ticket_types': ticket_type_stats,
                'injured_attendees': injured_list,
                'generated_at': timezone.now(),
                'generated_by': f"{request.user.firstname} {request.user.lastname}"
            }
            
            if report_format.lower() == 'json':
                return Response(context)
            
            buffer = BytesIO()

            pdf = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            def calc_percentage(part, whole):
                if whole == 0:
                    return 0
                return int((part / whole) * 100)
            

            pdf.setFont("Helvetica-Bold", 18)
            pdf.drawCentredString(width/2, height-50, f"Event Report: {event.title}")
            
            pdf.setFont("Helvetica", 12)
            pdf.drawCentredString(width/2, height-70, 
                f"{event.start_date.strftime('%B %d, %Y')} at {event.venue}, {event.location}")
            

            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(50, height-120, "Summary")

            pdf.rect(50, height-220, width-100, 80, stroke=1, fill=0)

            box_width = width-100
            item_width = box_width / 4
            

            summary_data = [
                ("Tickets Sold", stats['total_tickets_sold']),
                ("Attendees", stats['attended_count']),
                ("Revenue", stats['total_revenue']),
                ("Injuries", stats['injured_exits'])
            ]
            
            for i, (label, value) in enumerate(summary_data):
                x_pos = 50 + (i * item_width) + (item_width/2)
                
                pdf.setFont("Helvetica-Bold", 16)
                pdf.drawCentredString(x_pos, height-170, str(value))
                
                pdf.setFont("Helvetica", 10)
                pdf.drawCentredString(x_pos, height-190, label)
            

            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(50, height-250, "Attendance Statistics")

            header = ["Category", "Count", "Percentage"]
            header_width = [250, 100, 100]
            y_position = height-280
            
            for i, col in enumerate(header):
                x_start = 50 + sum(header_width[:i])
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(x_start, y_position, col)

            pdf.line(50, y_position-5, sum(header_width)+50, y_position-5)

            attendance_data = [
                ("Total Tickets Sold", stats['total_tickets_sold'], "100%"),
                ("Attendees (Used Tickets)", stats['attended_count'], 
                 f"{calc_percentage(stats['attended_count'], stats['total_tickets_sold'])}%"),
                ("Normal Exits", stats['normal_exits'], 
                 f"{calc_percentage(stats['normal_exits'], stats['attended_count'])}%"),
                ("Injury/Emergency Exits", stats['injured_exits'], 
                 f"{calc_percentage(stats['injured_exits'], stats['attended_count'])}%"),
                ("Still Inside", stats['still_inside'], 
                 f"{calc_percentage(stats['still_inside'], stats['attended_count'])}%"),
                ("Unused Tickets", stats['unused_tickets'], 
                 f"{calc_percentage(stats['unused_tickets'], stats['total_tickets_sold'])}%")
            ]
            
            y_position -= 20
            for row in attendance_data:
                for i, col in enumerate(row):
                    x_start = 50 + sum(header_width[:i])
                    pdf.setFont("Helvetica", 10)
                    pdf.drawString(x_start, y_position, str(col))
                y_position -= 20
            
            if y_position < 300:
                pdf.showPage()
                y_position = height - 50
                pdf.setFont("Helvetica-Bold", 14)
                pdf.drawString(50, y_position, "Ticket Type Breakdown")
                y_position -= 30
            else:
                y_position -= 30
                pdf.setFont("Helvetica-Bold", 14)
                pdf.drawString(50, y_position, "Ticket Type Breakdown")
                y_position -= 30
            
            header = ["Ticket Type", "Price", "Quantity Sold", "Revenue"]
            header_width = [200, 100, 100, 100]
            
            for i, col in enumerate(header):
                x_start = 50 + sum(header_width[:i])
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(x_start, y_position, col)
            
            pdf.line(50, y_position-5, sum(header_width)+50, y_position-5)
            
            y_position -= 20
            for tt in ticket_type_stats:
                row = [tt['name'], f"${tt['price']:.2f}", str(tt['sold']), f"${tt['revenue']:.2f}"]
                for i, col in enumerate(row):
                    x_start = 50 + sum(header_width[:i])
                    pdf.setFont("Helvetica", 10)
                    pdf.drawString(x_start, y_position, col)
                y_position -= 20
            
            if injured_list:
                if y_position < 200:
                    pdf.showPage()
                    y_position = height - 50
                else:
                    y_position -= 40
                
                pdf.setFont("Helvetica-Bold", 14)
                pdf.drawString(50, y_position, "Injury/Emergency Reports")
                y_position -= 30
                

                pdf.setFillColorRGB(1, 0.95, 0.8) 
                pdf.rect(50, y_position-30, width-100, 25, stroke=1, fill=1)
                pdf.setFillColorRGB(0, 0, 0)  # Back to black
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(60, y_position-15, "Note: This section contains sensitive medical information and should be handled with appropriate confidentiality.")
                
                y_position -= 50
                

                header = ["Attendee", "Contact", "Exit Time", "Exit Reason", "Notes"]
                header_width = [100, 120, 100, 80, 100]
                
                for i, col in enumerate(header):
                    x_start = 50 + sum(header_width[:i])
                    pdf.setFont("Helvetica-Bold", 10)
                    pdf.drawString(x_start, y_position, col)
                

                pdf.line(50, y_position-5, sum(header_width)+50, y_position-5)
                
                y_position -= 20
                for attendee in injured_list:

                    if y_position < 100:
                        pdf.showPage()
                        y_position = height - 50
                        

                        for i, col in enumerate(header):
                            x_start = 50 + sum(header_width[:i])
                            pdf.setFont("Helvetica-Bold", 10)
                            pdf.drawString(x_start, y_position, col)
                        
                        pdf.line(50, y_position-5, sum(header_width)+50, y_position-5)
                        y_position -= 20
                    
                    exit_time_str = attendee['exit_time'].strftime('%b %d, %Y %H:%M') if attendee['exit_time'] else "N/A"
                    

                    columns = [
                        attendee['name'],
                        f"{attendee['email']}\n{attendee['phone']}",
                        exit_time_str,
                        attendee['exit_reason'].title(),
                        attendee['notes'][:30] + ('...' if len(attendee['notes']) > 30 else '')
                    ]
                    
                    max_lines = 1
                    for i, col in enumerate(columns):
                        x_start = 50 + sum(header_width[:i])
                        pdf.setFont("Helvetica", 8)
                        

                        lines = col.split('\n')
                        if len(lines) > max_lines:
                            max_lines = len(lines)
                        
                        for j, line in enumerate(lines):
                            pdf.drawString(x_start, y_position - (j * 12), line)
                    
                    y_position -= (max_lines * 12) + 8  
            

            pdf.showPage() 
            pdf.setFont("Helvetica", 10)
            generated_at_str = context['generated_at'].strftime('%B %d, %Y at %H:%M')
            pdf.drawCentredString(width/2, 50, f"Report generated on {generated_at_str} by {context['generated_by']}")
            pdf.setFont("Helvetica", 8)
            pdf.drawCentredString(width/2, 30, "This report is confidential and intended for authorized personnel only.")
            
            # Save PDF
            pdf.save()
            
            buffer.seek(0)
            filename = f"event_report_{event.title.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            return Response(
                {'error': f'Error generating report: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )