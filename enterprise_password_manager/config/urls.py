from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='passwords:vault', permanent=False), name='home'),
    path('admin/', admin.site.urls),
    path('auth/', include(('apps.authentication.urls', 'authentication'), namespace='authentication')),
    path('users/', include(('apps.users.urls', 'users'), namespace='users')),
    path('vault/', include(('apps.passwords.urls', 'passwords'), namespace='passwords')),
    path('audit/', include(('apps.audit.urls', 'audit'), namespace='audit')),
    path('notifications/', include(('apps.notifications.urls', 'notifications'), namespace='notifications')),
    path('sso/', include(('apps.sso.urls', 'sso'), namespace='sso')),
    path('admin-dashboard/', include(('apps.admin_dashboard.urls', 'admin_dashboard'), namespace='admin_dashboard')),
    path('admin-dashboard/license/', include(('apps.licensing.urls', 'licensing'), namespace='licensing')),
    path('secrets/', include(('apps.secrets.urls', 'secrets'), namespace='secrets')),
    path('mailer/', include(('apps.mailer.urls', 'mailer'), namespace='mailer')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/auth/', include('apps.authentication.api_urls')),
    path('api/passwords/', include('apps.passwords.api_urls')),
    path('api/users/', include('apps.users.api_urls')),
    path('api/audit/', include('apps.audit.api_urls')),
]

if 'debug_toolbar' in settings.INSTALLED_APPS:
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
