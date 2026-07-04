from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('ops/', views.ops_dashboard, name='ops_dashboard'), 
    path('ops/assign/<int:fault_id>/', views.assign_job, name='assign_job'),
    path('ops/resolve/<int:fault_id>/', views.resolve_job, name='resolve_job'),
    path('tech/', views.technician_dashboard, name='technician_dashboard'),
    path('ops/resolve/<int:fault_id>/', views.resolve_job, name='resolve_job'),
    path('ops/dispute/<int:fault_id>/', views.dispute_job, name='dispute_job'), 
]
