from django.db import models
from django.conf import settings
from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator

class WaterPoint(models.Model):
    STATUS_CHOICES = [
        ('FUNCTIONAL', 'Functional (Green)'),
        ('MAINTENANCE', 'Needs Maintenance (Yellow)'),
        ('BROKEN', 'Broken Down (Red)'),
    ]
    
    point_id = models.CharField(max_length=20, unique=True, help_text="Unique asset tag, e.g., HW-BHL-001")
    location_name = models.CharField(max_length=100)
    lga = models.CharField(max_length=50, verbose_name="LGA")
    state = models.CharField(max_length=50, default="Katsina")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='FUNCTIONAL')
    last_inspected = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.point_id} - {self.location_name}"

# hydrowatch/models.py
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

class Technician(models.Model):
    name = models.CharField(max_length=100, default="")
    phone = models.CharField(max_length=20, default="")
    # 🌟 Added default="" here to prevent the prompt error:
    specialty = models.CharField(max_length=100, default="General Maintenance")
    lga_coverage = models.CharField(max_length=100, default="Unassigned")
    is_verified = models.BooleanField(default=False)
    
    # Star Rating system fields
    rating = models.FloatField(default=5.0, validators=[MinValueValidator(1.0), MaxValueValidator(5.0)])
    jobs_completed = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.rating}★)"

class FaultReport(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Assignment'),
        ('ASSIGNED', 'Technician Assigned'),
        ('FIXED', 'Repaired & Verified'),
        ('FAILED', 'Unresolved'),
	('DISPUTED', 'Disputed'),
    ]
    
    URGENCY_CHOICES = [
        ('LOW', 'Low (Minor leak)'),
        ('MEDIUM', 'Medium (Low pressure)'),
        ('HIGH', 'High (No water/Completely broken)'),
    ]

    water_point = models.ForeignKey(WaterPoint, on_delete=models.CASCADE, related_name='reports')
    reporter_phone = models.CharField(max_length=15)
    issue_description = models.TextField() # Keeps support for legacy queries
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='MEDIUM')
    
    # Combined status and timeline structures
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    is_resolved = models.BooleanField(default=False) # Supporting legacy view toggles
    date_reported = models.DateTimeField(auto_now_add=True) # Supporting legacy filters
    created_at = models.DateTimeField(auto_now_add=True) # Supporting premium dashboard mappings
    
    # Operations Tracking Fields
    assigned_technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True)
    quoted_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total money paid by community")
    
    # Earnings & Monetization Tracking Fields
    platform_fee_community = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Your earnings from community processing")
    platform_fee_technician = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Your earnings cut from the technician")
    is_paid_out = models.BooleanField(default=False, help_text="Has the technician been paid their net share?")

    def save(self, *args, **kwargs):
        # Synchronize legacy variable flags safely inside backend
        if self.status == 'FIXED':
            self.is_resolved = True
        else:
            self.is_resolved = False

        # 🆕 FIX: Ensure quoted_cost is treated as a Decimal/Float number, not a string
        if self.quoted_cost:
            try:
                cost_value = Decimal(str(self.quoted_cost))
            except (TypeError, ValueError):
                cost_value = Decimal('0.00')
        else:
            cost_value = Decimal('0.00')

        # DYNAMIC COMMISSION SCALING LOGIC BASED ON URGENCY
        if cost_value > 0:
            if self.urgency == 'LOW':
                comm_rate = Decimal('0.03')  # 3%
                tech_rate = Decimal('0.08')  # 8%
            elif self.urgency == 'HIGH':
                comm_rate = Decimal('0.08')  # 8% emergency levy
                tech_rate = Decimal('0.15')  # 15% emergency premium
            else:  # MEDIUM
                comm_rate = Decimal('0.05')  # 5%
                tech_rate = Decimal('0.10')  # 10%

            self.platform_fee_community = cost_value * comm_rate
            self.platform_fee_technician = cost_value * tech_rate
            
        super().save(*args, **kwargs)

    @property
    def total_platform_revenue(self):
        return self.platform_fee_community + self.platform_fee_technician

    @property
    def technician_net_payout(self):
        return self.quoted_cost - self.platform_fee_technician

    def __str__(self):
        return f"Fault {self.id} - {self.water_point.point_id} ({self.status})"


class MaintenanceLog(models.Model):
    # Enclosed safely to look directly upward at unified FaultReport
    report = models.OneToOneField(FaultReport, on_delete=models.CASCADE, related_name='maintenance_log')
    technician_name = models.CharField(max_length=100)
    action_taken = models.TextField()
    date_resolved = models.DateTimeField(auto_now_add=True)
    cost_incurred = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Fix for {self.report.water_point.point_id} by {self.technician_name}"