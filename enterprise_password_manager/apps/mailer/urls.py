from django.urls import path
from . import views

app_name = 'mailer'

urlpatterns = [
    path('', views.settings_view, name='settings'),
    path('settings/test/', views.settings_send_test, name='settings_send_test'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/<str:code>/edit/', views.template_edit, name='template_edit'),
    path('templates/<str:code>/preview/', views.template_preview, name='template_preview'),
    path('templates/test/', views.template_send_test, name='template_send_test'),
]
