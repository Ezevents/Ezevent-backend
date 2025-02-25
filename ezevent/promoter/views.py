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
from client.models import Purchase,PurchaseAttendee
from client.serializers import PurchaseSerializer
from django.utils import timezone
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from django.core.files.storage import default_storage
from django.http import HttpResponse
import qrcode
import os

class CreateEventView(generics.CreateAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

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

# class CreateTicketView(generics.CreateAPIView):
#     serializer_class = TicketTypeSerializer
#     permission_classes = [IsAuthenticated]

#     def perform_create(self, serializer):
#         event = Event.objects.get(id=self.kwargs['event_id'], promoter=self.request.user)
#         serializer.save(event=event)

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
        return Purchase.objects.filter(
            ticket_type__event__promoter=self.request.user,
            payment_status='pending',
            payment_screenshot__isnull=False, 
            is_approved_by_promoter=False
        ).order_by('-purchase_date')
    
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
            'approved_by': self.request.user.get_full_name(),
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

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save QR code temporarily
        temp_qr_path = os.path.join(temp_dir, f'temp_qr_{purchase.id}.png')
        img.save(temp_qr_path)
        
        tickets_dir = os.path.join(settings.MEDIA_ROOT, 'tickets')
        os.makedirs(tickets_dir, exist_ok=True)
        
        # Generate PDF with full path
        pdf_filename = f'ticket_{purchase.id}.pdf'
        pdf_path = os.path.join(tickets_dir, pdf_filename)
        
        # Generate PDF
        c = canvas.Canvas(pdf_path, pagesize=letter)
        
        # Add event details - use only standard fonts
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(letter[0]/2, 10*inch, purchase.ticket_type.event.title)
        
        c.setFont("Helvetica", 14)
        c.drawCentredString(letter[0]/2, 9.5*inch, f"Date: {purchase.ticket_type.event.start_date.strftime('%B %d, %Y')}")
        c.drawCentredString(letter[0]/2, 9.2*inch, f"Time: {purchase.ticket_type.event.start_date.strftime('%I:%M %p')} - {purchase.ticket_type.event.end_date.strftime('%I:%M %p')}")
        c.drawCentredString(letter[0]/2, 8.9*inch, f"Location: {purchase.ticket_type.event.location}")
        
        # Add ticket information
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(letter[0]/2, 8*inch, f"Ticket: {purchase.ticket_type.name}")
        
        c.setFont("Helvetica", 12)
        c.drawCentredString(letter[0]/2, 7.7*inch, f"Quantity: {purchase.quantity}")
        c.drawCentredString(letter[0]/2, 7.4*inch, f"Purchaser: {purchase.purchaser_email}")
        c.drawCentredString(letter[0]/2, 7.1*inch, f"Purchase Date: {purchase.purchase_date.strftime('%B %d, %Y')}")
        
        # Add attendee information if available
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
        
        # Add QR code
        c.drawImage(temp_qr_path, letter[0]/2 - 1.5*inch, 3*inch, width=3*inch, height=3*inch)
        
        c.setFont("Helvetica", 10)
        c.drawCentredString(letter[0]/2, 2.5*inch, "Please present this QR code at the event entrance")
        
        # Add footer - changed from Helvetica-Italic to Helvetica
        c.setFont("Helvetica", 8)
        c.drawCentredString(letter[0]/2, 1*inch, "This ticket is valid only for the named event and date.")
        c.drawCentredString(letter[0]/2, 0.8*inch, f"Ticket ID: {purchase.id}")
        
        c.save()
        
        # Clean up temporary file
        os.remove(temp_qr_path)

        try:
            os.remove(temp_qr_path)
        except:
            pass
        
        # Save PDF path to model
        with open(pdf_path, 'rb') as f:
            purchase.ticket_pdf = ContentFile(f.read(), name=pdf_filename)
        
        purchase.save()
        try:
        # Remove the local copy
            os.remove(pdf_path)
        except:
            pass
        
        return Response({
            'status': 'Payment approved',
            'message': 'PDF ticket has been generated and is available for the customer',
            'ticket_pdf_url': purchase.ticket_pdf.url
        })