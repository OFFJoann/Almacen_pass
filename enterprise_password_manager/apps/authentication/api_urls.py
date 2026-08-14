from django.urls import path
from . import api_views

urlpatterns = [
    path('login/', api_views.api_login, name='api_login'),
    path('logout/', api_views.api_logout, name='api_logout'),
    path('mfa/verify/', api_views.api_mfa_verify, name='api_mfa_verify'),
    path('me/', api_views.api_me, name='api_me'),
    path('token/login/', api_views.api_token_login, name='api_token_login'),
    path('token/mfa/', api_views.api_token_mfa_verify, name='api_token_mfa_verify'),
    path('token/session/', api_views.api_token_from_session, name='api_token_session'),
    path('token/logout/', api_views.api_token_logout, name='api_token_logout'),
]
