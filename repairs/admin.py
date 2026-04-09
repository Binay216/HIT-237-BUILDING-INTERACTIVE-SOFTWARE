from django.contrib import admin
from .models import (
    Community, Dwelling, TenantProfile, RepairRequest,
    MaintenanceLog, Notification, RepairFeedback
)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ['name', 'region', 'population', 'dwelling_count']
    list_filter = ['region']
    search_fields = ['name']


@admin.register(Dwelling)
class DwellingAdmin(admin.ModelAdmin):
    list_display = ['address', 'community', 'dwelling_type', 'bedrooms', 'meets_ncc_standards']
    list_filter = ['dwelling_type', 'meets_ncc_standards', 'community']
    search_fields = ['address', 'community__name']


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'dwelling', 'is_staff_member']
    list_filter = ['is_staff_member']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']


class MaintenanceLogInline(admin.TabularInline):
    model = MaintenanceLog
    extra = 0
    readonly_fields = ['created_at']


@admin.register(RepairRequest)
class RepairRequestAdmin(admin.ModelAdmin):
    list_display = ['title', 'tenant', 'issue_type', 'priority', 'status', 'created_at']
    list_filter = ['status', 'priority', 'issue_type', 'dwelling__community']
    search_fields = ['title', 'description', 'tenant__user__username']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    inlines = [MaintenanceLogInline]


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ['repair_request', 'author', 'status_change', 'created_at']
    list_filter = ['status_change']
    readonly_fields = ['created_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at']


@admin.register(RepairFeedback)
class RepairFeedbackAdmin(admin.ModelAdmin):
    list_display = ['repair_request', 'tenant', 'rating', 'created_at']
    list_filter = ['rating']
    readonly_fields = ['created_at']
