from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.UserListView.as_view(), name='list'),
    path('create/', views.UserCreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.UserDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.UserUpdateView.as_view(), name='edit'),
    path('<uuid:pk>/delete/', views.UserDeleteView.as_view(), name='delete'),
    path('<uuid:pk>/toggle-active/', views.user_toggle_active, name='toggle_active'),
    path('<uuid:pk>/reset-password/', views.user_reset_password, name='reset_password'),
    path('groups/', views.GroupListView.as_view(), name='group_list'),
    path('groups/create/', views.GroupCreateView.as_view(), name='group_create'),
    path('groups/<uuid:pk>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('groups/<uuid:pk>/edit/', views.GroupUpdateView.as_view(), name='group_edit'),
    path('groups/<uuid:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),
]
