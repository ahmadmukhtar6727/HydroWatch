from django.contrib import admin
from .models import WaterPoint, FaultReport, MaintenanceLog, Technician

@admin.register(WaterPoint)
class WaterPointAdmin(admin.ModelAdmin):
    list_display = ('point_id', 'location_name', 'lga', 'status', 'last_inspected')
    list_filter = ('status', 'lga')
    search_fields = ('point_id', 'location_name')



@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    # Removed lga_coverage and is_verified from list_display
    list_display = ('id', 'name', 'specialty', 'rating', 'jobs_completed')
    
    # Removed fields from list_filter or set it only to fields that exist
    list_filter = ('specialty', 'rating') 
    search_fields = ('name', 'specialty')

@admin.register(FaultReport)
class FaultReportAdmin(admin.ModelAdmin):
    # CHANGED: 'date_reported' -> 'created_at', and 'is_resolved' -> 'status'
    list_display = ('id', 'water_point', 'urgency', 'status', 'created_at', 'assigned_technician', 'quoted_cost')
    list_filter = ('status', 'urgency', 'created_at')
    search_fields = ('reporter_phone', 'description', 'water_point__point_id')

@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'report', 'technician_name', 'cost_incurred')
    search_fields = ('technician_name', 'action_taken')