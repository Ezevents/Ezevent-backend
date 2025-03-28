from rest_framework import serializers
from .models import Event, TicketType

class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = '__all__'
        read_only_fields = ('remaining',)

    def validate(self, data):
        if data['sale_start_date'] >= data['sale_end_date']:
            raise serializers.ValidationError("Sale end date must be after start date")
        if data['sale_end_date'] > data['event'].start_date:
            raise serializers.ValidationError("Ticket sales must end before event starts")
        return data

class EventSerializer(serializers.ModelSerializer):
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ('promoter', 'created_at', 'updated_at')
        extra_kwargs = {
            'image': {'required': False}, 
            'profile_pic': {'required': False}
        }

    def validate(self, data):
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("End date must be after start date")
        return data