from django.urls import path
from . import views

app_name = 'secrets'

urlpatterns = [
    path('', views.secret_list, name='list'),
    path('trash/', views.secret_trash, name='trash'),
    path('create/<str:secret_type>/', views.secret_create, name='create'),
    path('<uuid:pk>/', views.secret_detail, name='detail'),
    path('<uuid:pk>/edit/', views.secret_edit, name='edit'),
    path('<uuid:pk>/delete/', views.secret_delete, name='delete'),
    path('<uuid:pk>/mark-obsolete/', views.secret_mark_obsolete, name='mark_obsolete'),
    path('<uuid:pk>/restore/', views.secret_restore, name='restore'),
    path('<uuid:pk>/permanent-delete/', views.secret_permanent_delete, name='permanent_delete'),
    path('<uuid:pk>/share/', views.secret_share, name='share'),
    path('share/<uuid:share_id>/revoke/', views.secret_revoke_share, name='revoke_share'),
    path('share/<uuid:share_id>/update-permission/', views.secret_update_share_permission, name='update_share_permission'),
]
