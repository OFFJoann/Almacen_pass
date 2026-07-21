from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('logs/', views.AuditLogListView.as_view(), name='log_list'),
    path('logs/<uuid:pk>/', views.AuditLogDetailView.as_view(), name='log_detail'),
    path('user/<uuid:user_id>/', views.user_activity_view, name='user_activity'),
    path('my-activity/', views.my_activity_view, name='my_activity'),
]
