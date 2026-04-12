from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Auth (FBVs — procedural login/register flow)
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Profile & Password (FBVs — hybrid form handling)
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.password_change_view, name='password_change'),

    # Dashboard
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('dashboard/tenant/', views.TenantDashboardView.as_view(), name='tenant_dashboard'),
    path('dashboard/staff/', views.StaffDashboardView.as_view(), name='staff_dashboard'),

    # Repair Requests (CBVs for CRUD, FBVs for actions)
    path('requests/', views.RepairRequestListView.as_view(), name='request_list'),
    path('requests/create/', views.RepairRequestCreateView.as_view(), name='request_create'),
    path('requests/<int:pk>/', views.RepairRequestDetailView.as_view(), name='request_detail'),
    path('requests/<int:pk>/edit/', views.RepairRequestUpdateView.as_view(), name='request_edit'),
    path('requests/<int:pk>/delete/', views.RepairRequestDeleteView.as_view(), name='request_delete'),
    path('requests/<int:pk>/cancel/', views.cancel_request, name='cancel_request'),
    path('requests/<int:pk>/update-status/', views.update_request_status, name='update_request_status'),
    path('requests/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('requests/<int:pk>/feedback/', views.submit_feedback, name='submit_feedback'),

    # Communities (CBVs — staff only)
    path('communities/', views.CommunityListView.as_view(), name='community_list'),
    path('communities/<int:pk>/', views.CommunityDetailView.as_view(), name='community_detail'),

    # Dwellings (CBVs)
    path('dwellings/', views.DwellingListView.as_view(), name='dwelling_list'),
    path('dwelling/<int:pk>/', views.DwellingDetailView.as_view(), name='dwelling_detail'),

    # Analytics & Export
    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),
    path('export/csv/', views.export_csv, name='export_csv'),

    # Notifications (CBV for list, FBVs for actions)
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
