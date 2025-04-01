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
    event_title = serializers.CharField(source='ticket_type.event.title', read_only=True)
    ticket_type_name = serializers.CharField(source='ticket_type.name', read_only=True)
    class Meta:
        model = Purchase
        fields = [
            'id', 'ticket_type', 'ticket_type_name', 'quantity', 'total_amount', 
            'purchase_date', 'payment_status', 'payment_method', 'purchaser_email', 
            'purchaser_phone', 'payment_screenshot', 'is_approved_by_promoter', 
            'transaction_reference', 'attendees', 'attendee_details', 'event_title', 
            'ticket_pdf_url'
        ]
        read_only_fields = [
            'id', 'purchase_date', 'payment_status', 'transaction_reference', 
            'attendee_details', 'is_approved_by_promoter', 'ticket_pdf_url'
        ]
    
    def get_attendee_details(self, obj):
        # Get the actual Attendee objects through the relationship
        purchase_attendees = PurchaseAttendee.objects.filter(purchase=obj)
        attendees = [pa.attendee for pa in purchase_attendees]
        return AttendeeSerializer(attendees, many=True).data
    
    def get_payment_screenshot_url(self, obj):
        # Return the payment screenshot URL if it exists
        return obj.payment_screenshot if obj.payment_screenshot else None
    
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
        if ticket_type.remaining >= quantity:
            ticket_type.remaining -= quantity
            ticket_type.save()
        else:
            # Handle insufficient tickets scenario
            purchase.delete()
            raise serializers.ValidationError("Not enough tickets available")
        
        return purchase