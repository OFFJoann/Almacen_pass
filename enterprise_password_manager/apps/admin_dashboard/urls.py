from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('obsolete/', views.obsolete_records, name='obsolete'),
    path('obsolete/password/<uuid:pk>/delete/', views.obsolete_delete_password, name='obsolete_delete_password'),
    path('obsolete/secret/<uuid:pk>/delete/', views.obsolete_delete_secret, name='obsolete_delete_secret'),
]
