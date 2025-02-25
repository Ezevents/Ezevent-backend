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