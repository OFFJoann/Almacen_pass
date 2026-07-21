from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('<uuid:pk>/read/', views.mark_as_read, name='mark_read'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
    path('unread-count/', views.get_unread_count, name='unread_count'),
]
