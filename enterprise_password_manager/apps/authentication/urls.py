from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('mfa/verify/', views.mfa_verify, name='mfa_verify'),
    path('mfa/setup/', views.setup_mfa, name='setup_mfa'),
    path('mfa/disable/', views.disable_mfa, name='disable_mfa'),
    path('force-password-change/', views.force_password_change_view, name='force_password_change'),
    path('emergency-contact/', views.set_emergency_contact, name='emergency_contact'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/<str:uidb64>/<str:token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('lockout/', views.lockout_view, name='lockout'),
]
