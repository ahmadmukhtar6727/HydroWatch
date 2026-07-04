from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Sum, Avg 
from .models import WaterPoint, FaultReport, MaintenanceLog, Technician
from django.utils import timezone
from django.utils import timezone


def home(request):
    # Handle incoming fault reports from the community (Keep existing logic)
    if request.method == 'POST':
        point_id = request.POST.get('water_point_id')
        phone = request.POST.get('reporter_phone')
        description = request.POST.get('issue_description')
        urgency = request.POST.get('urgency')
        
        try:
            selected_point = WaterPoint.objects.get(id=point_id)
            FaultReport.objects.create(
                water_point=selected_point,
                reporter_phone=phone,
                issue_description=description,
                urgency=urgency
            )
            if urgency == 'HIGH':
                selected_point.status = 'BROKEN'
                selected_point.save()
            
            messages.success(request, "Thank you! Your report has been submitted, and the dashboard has been updated.")
            return redirect('home')
        except WaterPoint.DoesNotExist:
            messages.error(request, "Error: Selected water point does not exist.")
            return redirect('home')

    # --- ADVANCED DATA ANALYTICS PIPELINE FOR JUDGES ---
    total_assets = WaterPoint.objects.count()
    broken_assets = WaterPoint.objects.filter(status='BROKEN').count()
    resolved_repairs = FaultReport.objects.filter(is_resolved=True).count()
    
    # Calculate financial metrics from the MaintenanceLogs
    financial_data = MaintenanceLog.objects.aggregate(
        total_spent=Sum('cost_incurred'),
        avg_cost=Avg('cost_incurred')
    )
    total_spent = financial_data['total_spent'] or 0.00
    avg_cost = financial_data['avg_cost'] or 0.00

    # 🆕 ADD THIS: Calculate platform revenue generated for the homepage metrics
    platform_revenue_stats = FaultReport.objects.filter(status='FIXED').aggregate(
        comm_fees=Sum('platform_fee_community'),
        tech_fees=Sum('platform_fee_technician')
    )
    home_platform_profit = (platform_revenue_stats['comm_fees'] or 0) + (platform_revenue_stats['tech_fees'] or 0)

    # Fetch data for the directory table
    water_points = WaterPoint.objects.all().order_by('point_id')

    context = {
        'water_points': water_points,
        'total_assets': total_assets,
        'broken_assets': broken_assets,
        'resolved_repairs': resolved_repairs,
        'total_spent': total_spent,
        'avg_cost': avg_cost,
        'home_platform_profit': home_platform_profit, # 🆕 Passed to HTML
    }
    return render(request, 'hydrowatch/home.html', context)


def technician_dashboard(request):
    # If the technician submits a repair log
    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        tech_name = request.POST.get('technician_name')
        action = request.POST.get('action_taken')
        cost = request.POST.get('cost_incurred', 0.00)
        
        # Get the fault report
        report = get_object_or_404(FaultReport, id=report_id)
        
        # 1. Create the Maintenance Log
        MaintenanceLog.objects.create(
            report=report,
            technician_name=tech_name,
            action_taken=action,
            cost_incurred=cost
        )
        
        # 2. Mark the report as resolved
        report.is_resolved = True
        report.save()
        
        # 3. Automatically restore the Water Point status back to FUNCTIONAL
        water_point = report.water_point
        water_point.status = 'FUNCTIONAL'
        water_point.save()
        
        messages.success(request, f"Success! Maintenance log saved for {water_point.point_id}. Asset restored to Functional.")
        return redirect('technician_dashboard')

    # Fetch all reports that are NOT yet resolved, ordered by newest first
    open_reports = FaultReport.objects.filter(is_resolved=False).order_by('-date_reported')
    
    # Fetch completed logs for the history panel
    past_logs = MaintenanceLog.objects.all().order_by('-date_resolved')[:5]

    context = {
        'open_reports': open_reports,
        'past_logs': past_logs,
    }
    return render(request, 'hydrowatch/technician.html', context)

def ops_dashboard(request):
    # Fetch active cases and available techs
    pending_faults = FaultReport.objects.filter(status='PENDING').order_by('-created_at')
    active_jobs = FaultReport.objects.filter(status='ASSIGNED')
    completed_jobs = FaultReport.objects.filter(status='FIXED')
    technicians = Technician.objects.all()
    
    # FIX: Calculate revenue from ANY report where a cost was quoted (> 0)
    # This prevents status string mismatches from hiding your profit balances!
    total_revenue_stats = FaultReport.objects.filter(quoted_cost__gt=0).aggregate(
        comm_fees=Sum('platform_fee_community'),
        tech_fees=Sum('platform_fee_technician')
    )
    
    community_earnings = total_revenue_stats['comm_fees'] or 0
    technician_earnings = total_revenue_stats['tech_fees'] or 0
    total_platform_profit = community_earnings + technician_earnings

    context = {
        'pending_faults': pending_faults,
        'active_jobs': active_jobs,
        'completed_jobs': completed_jobs,
        'technicians': technicians,
        'community_earnings': community_earnings,
        'technician_earnings': technician_earnings,
        'total_platform_profit': total_platform_profit,
	'disputed_jobs': FaultReport.objects.filter(status='DISPUTED'),
    }
    return render(request, 'hydrowatch/ops_dashboard.html', context)

def assign_job(request, fault_id):
    if request.method == "POST":
        fault = get_object_or_404(FaultReport, id=fault_id)
        tech_id = request.POST.get('technician_id')
        cost = request.POST.get('quoted_cost')
        
        fault.assigned_technician_id = tech_id
        fault.quoted_cost = cost
        fault.status = 'ASSIGNED'
        fault.save()
        
        messages.success(request, f"Job assigned successfully! Calculated expected platform share.")
    return redirect('ops_dashboard')

from django.shortcuts import redirect
from django.utils import timezone
from .models import MaintenanceLog, FaultReport, Technician

def resolve_job(request, fault_id):  
    if request.method == "POST":
        job = None
        
        # 1. Look up the log record via all possible routes
        try:
            job = MaintenanceLog.objects.get(id=fault_id)
        except MaintenanceLog.DoesNotExist:
            try:
                job = MaintenanceLog.objects.get(report_id=fault_id)
            except MaintenanceLog.DoesNotExist:
                try:
                    report = FaultReport.objects.get(id=fault_id)
                    job = MaintenanceLog.objects.filter(report=report).first()
                except FaultReport.DoesNotExist:
                    pass

        # 2. Process updates if the log is successfully caught
        if job:
            # Handle Technician stars calculation safely
            if job.technician_name:
                try:
                    tech = Technician.objects.get(name=job.technician_name)
                    given_stars = float(request.POST.get('performance_rating', 5))
                    total_jobs = tech.jobs_completed or 0
                    tech.rating = ((tech.rating * total_jobs) + given_stars) / (total_jobs + 1)
                    tech.jobs_completed += 1
                    tech.save()
                except Technician.DoesNotExist:
                    pass

            # Update the maintenance entry record details
            job.action_taken = "Resolved and approved via Operations Control"
            job.date_resolved = timezone.now()
            
            # Target both uppercase and lowercase status fields just in case
            if hasattr(job, 'status'):
                job.status = 'RESOLVED'
            job.save()
            
            # Force status updates on the attached report profile
            if job.report:
                job.report.status = 'RESOLVED'
                if hasattr(job.report, 'is_resolved'):
                    job.report.is_resolved = True
                job.report.save()
        
        # 3. CRITICAL GLOBAL OVERRIDE: 
        # Directly catch the target FaultReport by its primary key ID and force its status update.
        # This fixes the main homepage dashboard if it loads via FaultReport rows!
        try:
            direct_report = FaultReport.objects.get(id=fault_id)
            direct_report.status = 'RESOLVED'  # Sets standard status strings
            if hasattr(direct_report, 'is_resolved'):
                direct_report.is_resolved = True  # Sets boolean tracking columns if present
            direct_report.save()
        except FaultReport.DoesNotExist:
            pass
            
    return redirect('/ops/')

def dispute_job(request, fault_id):
    """Flags a repair log as failed or disputed by the community, locking funds."""
    fault = FaultReport.objects.get(id=fault_id)
    fault.status = 'DISPUTED'
    
    # Freeze the platform platform payouts down to zero until resolved
    fault.platform_fee_community = 0
    fault.platform_fee_technician = 0
    fault.save()
    
    messages.error(request, f"🚨 Escrow Frozen! Repair failure reported for {fault.water_point.point_id}. Investigation opened.")
    return redirect('ops_dashboard')