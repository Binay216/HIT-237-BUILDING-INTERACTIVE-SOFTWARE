from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Profile & Password
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.password_change_view, name='password_change'),

    # Dashboard
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('dashboard/tenant/', views.tenant_dashboard, name='tenant_dashboard'),
    path('dashboard/staff/', views.staff_dashboard, name='staff_dashboard'),

    # Repair Requests
    path('requests/', views.request_list, name='request_list'),
    path('requests/create/', views.request_create, name='request_create'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('requests/<int:pk>/edit/', views.request_edit, name='request_edit'),
    path('requests/<int:pk>/delete/', views.request_delete, name='request_delete'),
    path('requests/<int:pk>/cancel/', views.cancel_request, name='cancel_request'),
    path('requests/<int:pk>/update-status/', views.update_request_status, name='update_request_status'),
    path('requests/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('requests/<int:pk>/feedback/', views.submit_feedback, name='submit_feedback'),

    # Communities (Staff)
    path('communities/', views.community_list, name='community_list'),
    path('communities/<int:pk>/', views.community_detail, name='community_detail'),

    # Dwellings
    path('dwellings/', views.dwelling_list, name='dwelling_list'),
    path('dwelling/<int:pk>/', views.dwelling_detail, name='dwelling_detail'),

    # Analytics & Export (Staff)
    path('analytics/', views.analytics_view, name='analytics'),
    path('export/csv/', views.export_csv, name='export_csv'),

    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
