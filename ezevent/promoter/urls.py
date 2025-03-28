from django.urls import path
from . import views

urlpatterns = [
    path('create_event', views.CreateEventView.as_view(), name='create_event'),
    path('list_events', views.ListEventsView.as_view(), name='list_events'),
    path('event_detail/<int:event_id>/', views.EventDetailView.as_view(), name='event_detail'),
    path('update_event/<int:event_id>/', views.UpdateEventView.as_view(), name='update_event'),
    path('delete_event/<int:event_id>/', views.DeleteEventView.as_view(), name='delete_event'),
    path('event/<int:event_id>/publish/', views.PublishEventView.as_view(), name='publish_event'),
    
    path('create_ticket/<int:event_id>/', views.CreateTicketView.as_view(), name='create_ticket'),
    path('list_tickets/<int:event_id>/', views.ListTicketsView.as_view(), name='list_tickets'),
    path('update_ticket/<int:ticket_id>/', views.UpdateTicketView.as_view(), name='update_ticket'),
    path('delete_ticket/<int:ticket_id>/', views.DeleteTicketView.as_view(), name='delete_ticket'),

    path('event_summary/<int:event_id>/', views.EventSummaryView.as_view(), name='event_summary'),

    path('search_events', views.SearchEventsView.as_view(), name='search_events'),
    path('bulk_create_tickets/<int:event_id>/', views.BulkCreateTicketsView.as_view(), name='bulk_create_tickets'),
    path('event_analytics', views.EventAnalyticsView.as_view(), name='event_analytics'),
    path('event_analytics/<int:event_id>/', views.SingleEventAnalyticsView.as_view(), name='single_event_analytics'),

    path('pending_payments', views.PendingPaymentsListView.as_view(), name='pending_payments'),
    path('purchase/<int:purchase_id>/approve', views.PromoterPaymentApprovalView.as_view(), name='approve_payment'),
    path('scan_ticket', views.ScanTicketView.as_view(), name='scan_ticket'),
    path('scan_exit', views.ScanTicketExitView.as_view(), name='scan_ticket_exit'),
    path('generate_scanner_url', views.GenerateScannerUrlView.as_view(), name='generate_scanner_url'),

    path('tickets_details/', views.TicketDetailsView.as_view(), name='ticket-list'),
    path('tickets_details/<int:ticket_id>/', views.TicketDetailsView.as_view(), name='ticket-detail'),

    path('events/<int:event_id>/report/', views.EventReportPDFView.as_view(), name='event-report-pdf'),
]