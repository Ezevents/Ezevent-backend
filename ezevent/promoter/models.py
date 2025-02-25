# models.py
from django.db import models
from auths.models import Users

class Event(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed')
    ]
    
    promoter = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    venue = models.CharField(max_length=200)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    image = models.ImageField(upload_to='event_images/', null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    category = models.CharField(max_length=100, null=True, blank=True)
    max_capacity = models.PositiveIntegerField()

    class Meta:
        ordering = ['-start_date']
        app_label = 'promoter'

    def __str__(self):
        return self.title

class TicketType(models.Model):
    event = models.ForeignKey(Event, related_name='ticket_types', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    remaining = models.PositiveIntegerField()
    sale_start_date = models.DateTimeField()
    sale_end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event.title} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # If creating new ticket type
            self.remaining = self.quantity
        super().save(*args, **kwargs)


