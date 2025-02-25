from rest_framework import serializers
from .models import Attendee, Purchase, PurchaseAttendee
class AttendeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendee
        fields = ['id', 'first_name', 'last_name', 'email', 'phone']

class PurchaseSerializer(serializers.ModelSerializer):
    attendees = AttendeeSerializer(many=True, required=False)
    
    class Meta:
        model = Purchase
        fields = ['id', 'ticket_type', 'quantity', 'total_amount', 'purchase_date', 
                 'payment_status', 'payment_method', 'purchaser_email', 
                 'purchaser_phone', 'attendees']
        read_only_fields = ['id', 'purchase_date', 'payment_status', 'transaction_reference']
    
    def create(self, validated_data):
        attendees_data = validated_data.pop('attendees', [])
        
        # Calculating total amount
        ticket_type = validated_data.get('ticket_type')
        quantity = validated_data.get('quantity', 1)
        validated_data['total_amount'] = ticket_type.price * quantity
        
        # Creating the purchase
        purchase = Purchase.objects.create(**validated_data)
        
        # Creating attendees
        for attendee_data in attendees_data:
            attendee, _ = Attendee.objects.get_or_create(
                email=attendee_data['email'],
                defaults=attendee_data
            )
            PurchaseAttendee.objects.create(purchase=purchase, attendee=attendee)
        
        # Update ticket availability
        ticket_type.remaining -= quantity
        ticket_type.save()
        
        return purchase