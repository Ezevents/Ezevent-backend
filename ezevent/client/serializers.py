from rest_framework import serializers
from .models import Attendee, Purchase, PurchaseAttendee
class AttendeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendee
        fields = ['id', 'first_name', 'last_name', 'email', 'phone']

class PurchaseSerializer(serializers.ModelSerializer):
    attendees = serializers.ListField(
        child=AttendeeSerializer(), 
        write_only=True,
        required=False
    )
    attendee_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Purchase
        fields = ['id', 'ticket_type', 'quantity', 'total_amount', 'purchase_date', 
                 'payment_status', 'payment_method', 'purchaser_email', 
                 'purchaser_phone', 'attendees', 'attendee_details']
        read_only_fields = ['id', 'purchase_date', 'payment_status', 'transaction_reference', 'attendee_details']
    
    def get_attendee_details(self, obj):
        # Get the actual Attendee objects through the relationship
        purchase_attendees = PurchaseAttendee.objects.filter(purchase=obj)
        attendees = [pa.attendee for pa in purchase_attendees]
        return AttendeeSerializer(attendees, many=True).data
    
    def create(self, validated_data):
        # Extract attendees data before creating purchase
        attendees_data = validated_data.pop('attendees', [])
        
        # Calculate total amount if not provided
        if 'total_amount' not in validated_data:
            ticket_type = validated_data.get('ticket_type')
            quantity = validated_data.get('quantity', 1)
            validated_data['total_amount'] = ticket_type.price * quantity
        
        # Create the purchase
        purchase = Purchase.objects.create(**validated_data)
        
        # Create attendees
        for attendee_data in attendees_data:
            attendee = Attendee.objects.create(**attendee_data)
            PurchaseAttendee.objects.create(purchase=purchase, attendee=attendee)
        
        # Update ticket availability
        ticket_type = validated_data.get('ticket_type')
        quantity = validated_data.get('quantity', 1)
        ticket_type.remaining -= quantity
        ticket_type.save()
        
        return purchase