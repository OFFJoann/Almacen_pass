from django.urls import path
from . import views

app_name = 'mailer'

urlpatterns = [
    path('', views.settings_view, name='settings'),
    path('settings/test/', views.settings_send_test, name='settings_send_test'),
    path('groups/', views.group_list, name='groups'),
    path('groups/create/', views.group_create, name='group_create'),
    path('groups/<uuid:pk>/', views.group_detail, name='group_detail'),
    path('groups/<uuid:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<uuid:pk>/delete/', views.group_delete, name='group_delete'),
    path('groups/<uuid:pk>/recipients/add/', views.group_recipient_add, name='group_recipient_add'),
    path('groups/<uuid:pk>/recipients/<uuid:recipient_id>/delete/', views.group_recipient_delete, name='group_recipient_delete'),
    path('groups/<uuid:pk>/events/<uuid:event_id>/toggle/', views.group_event_toggle, name='group_event_toggle'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/<str:code>/edit/', views.template_edit, name='template_edit'),
    path('templates/<str:code>/preview/', views.template_preview, name='template_preview'),
]
