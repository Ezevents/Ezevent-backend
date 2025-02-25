from django.urls import path 
from . import views

urlpatterns = [
    path('events/<int:event_id>/promoter-contacts', views.GetPromoterContactsView.as_view(), name='promoter_contacts'),
    path('purchase/<int:purchase_id>/submit-payment', views.SubmitPaymentProofView.as_view(), name='submit_payment'),
    path('purchase/<int:purchase_id>', views.PurchaseDetailView.as_view(), name='purchase_detail'),
    path('events/available', views.AvailableEventsView.as_view(), name='available_events'),
    path('events/<int:event_id>/tickets', views.EventTicketsView.as_view(), name='event_tickets'),
    path('purchase/create', views.CreatePurchaseView.as_view(), name='create_purchase'),
    path('purchase/<int:purchase_id>/payment', views.InitiatePaymentView.as_view(), name='initiate_payment'),
]