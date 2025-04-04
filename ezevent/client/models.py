from django.db import models
from django.contrib.auth import get_user_model
from promoter.models import TicketType
from auths.models import Users

class Attendee(models.Model):
    """Model for individuals attending the event (one purchase can have multiple attendees)"""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Purchase(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded')
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mtn', 'MTN Mobile Money'),
        ('airtel', 'Airtel Money')
    ]
    
    user = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True) 
    ticket_type = models.ForeignKey('promoter.TicketType', on_delete=models.PROTECT, related_name='purchases')
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=0)
    purchase_date = models.DateTimeField(auto_now_add=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)
    purchaser_email = models.EmailField()
    purchaser_phone = models.CharField(max_length=20)
    payment_screenshot = models.CharField(max_length=500, null=True, blank=True)
    is_approved_by_promoter = models.BooleanField(default=False)
    approval_date = models.DateTimeField(null=True, blank=True)
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    # ticket_pdf = models.FileField(upload_to='tickets/', null=True, blank=True)
    ticket_pdf_url = models.URLField(max_length=500, null=True, blank=True)
    
    def __str__(self):
        return f"Purchase #{self.id} - {self.ticket_type.event.title}"

class PurchaseAttendee(models.Model):
    """Junction model linking purchases to attendees"""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='attendees')
    attendee = models.ForeignKey(Attendee, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('purchase', 'attendee')

class TicketPDF(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='ticket_pdfs')
    attendee = models.ForeignKey(Attendee, on_delete=models.CASCADE)
    pdf_url = models.URLField(max_length=500, null=True, blank=True)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    time_spent = models.DurationField(null=True, blank=True)
    exit_reason = models.CharField(max_length=50, choices=[
        ('normal', 'Normal Exit'),
        ('injured', 'Injured'),
        ('emergency', 'Emergency'),
    ], default='normal')
    injury_notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Ticket for {self.attendee.first_name} {self.attendee.last_name}"
    