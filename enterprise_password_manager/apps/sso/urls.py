from django.urls import path
from . import views

app_name = 'sso'

urlpatterns = [
    path('settings/', views.sso_settings, name='settings'),
    path('configure/', views.sso_configure, name='configure'),
    path('test-connection/', views.sso_test_connection, name='test_connection'),
    path('toggle/', views.sso_toggle, name='toggle'),
    path('login/', views.sso_login, name='login'),
    path('callback/', views.sso_callback, name='callback'),
]
