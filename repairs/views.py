import csv

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Q, Count, Avg, F
from django.db.models.functions import TruncMonth
from django.http import StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.utils import timezone

from .models import (
    RepairRequest, Dwelling, MaintenanceLog, Community,
    Notification, RepairFeedback
)
from .forms import (
    RegistrationForm, RepairRequestForm, MaintenanceLogForm,
    StatusUpdateForm, RequestFilterForm, TenantCommentForm,
    ProfileEditForm, RepairFeedbackForm
)
from .decorators import login_required_with_message, tenant_required, staff_required


# ── Home ─────────────────────────────────────────────────────────

def home(request):
    context = {
        'community_count': Community.objects.count(),
        'dwelling_count': Dwelling.objects.count(),
    }
    if request.user.is_authenticated:
        context['total_requests'] = RepairRequest.objects.count()
        context['completed_requests'] = RepairRequest.objects.completed().count()
    return render(request, 'home.html', context)


# ── Auth ─────────────────────────────────────────────────────────

def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful. Welcome!')
            return redirect('tenant_dashboard')
    else:
        form = RegistrationForm()
    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            if hasattr(user, 'profile') and user.profile.is_staff_member:
                return redirect('staff_dashboard')
            return redirect('tenant_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'auth/login.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'You have been logged out.')
    return redirect('home')


# ── Dashboard ────────────────────────────────────────────────────

@login_required_with_message
def dashboard_redirect(request):
    """Redirect to the appropriate dashboard based on user role."""
    if hasattr(request.user, 'profile') and request.user.profile.is_staff_member:
        return redirect('staff_dashboard')
    return redirect('tenant_dashboard')


@tenant_required
def tenant_dashboard(request):
    profile = request.user.profile
    overdue_requests = RepairRequest.objects.filter(
        tenant=profile
    ).active()
    overdue_list = [r for r in overdue_requests if r.is_overdue()]

    context = {
        'profile': profile,
        'open_count': profile.open_requests.count(),
        'completed_count': profile.completed_requests.count(),
        'overdue_count': len(overdue_list),
        'recent_requests': RepairRequest.objects.filter(
            tenant=profile
        ).select_related('dwelling').order_by('-created_at')[:5],
        'ncc_warning': (
            profile.dwelling and not profile.dwelling.meets_ncc_standards
        ),
    }
    return render(request, 'dashboard/tenant_dashboard.html', context)


@staff_required
def staff_dashboard(request):
    context = {
        'pending_count': RepairRequest.objects.pending().count(),
        'in_progress_count': RepairRequest.objects.in_progress().count(),
        'completed_count': RepairRequest.objects.completed().count(),
        'overdue_count': RepairRequest.objects.overdue().count(),
        'stats_by_issue': RepairRequest.objects.stats_by_issue_type(),
        'stats_by_community': RepairRequest.objects.stats_by_community(),
        'urgent_requests': RepairRequest.objects.filter(
            priority='EMERGENCY'
        ).active().select_related(
            'dwelling', 'dwelling__community'
        )[:5],
        'recent_requests': RepairRequest.objects.active().select_related(
            'tenant', 'dwelling', 'dwelling__community'
        ).order_by('-created_at')[:10],
    }
    return render(request, 'dashboard/staff_dashboard.html', context)


# ── Repair Requests (Tenant) ────────────────────────────────────

@tenant_required
def request_create(request):
    profile = request.user.profile

    if not profile.dwelling:
        messages.error(
            request,
            'You need to be assigned to a dwelling before submitting requests. '
            'Please contact your housing coordinator.'
        )
        return redirect('tenant_dashboard')

    if request.method == 'POST':
        form = RepairRequestForm(request.POST, request.FILES)
        if form.is_valid():
            repair = form.save(commit=False)
            repair.tenant = profile
            repair.dwelling = profile.dwelling
            repair.save()
            messages.success(request, 'Repair request submitted successfully.')
            return redirect('request_detail', pk=repair.pk)
    else:
        form = RepairRequestForm()
    return render(request, 'repairs/request_create.html', {'form': form})


@login_required_with_message
def request_detail(request, pk):
    repair = get_object_or_404(
        RepairRequest.objects.select_related(
            'tenant__user', 'dwelling__community', 'assigned_to__user'
        ),
        pk=pk
    )

    # Security: tenants can only see their own requests
    profile = request.user.profile
    if profile.is_tenant and repair.tenant != profile:
        messages.error(request, 'You can only view your own requests.')
        return redirect('request_list')

    logs = repair.logs.select_related('author__user').all()

    # Staff can add maintenance logs and update status
    log_form = None
    status_form = None
    comment_form = None

    if profile.is_staff_member:
        log_form = MaintenanceLogForm()
        status_form = StatusUpdateForm(initial={'status': repair.status})
    elif profile.is_tenant and repair.is_active:
        comment_form = TenantCommentForm()

    context = {
        'repair': repair,
        'logs': logs,
        'log_form': log_form,
        'status_form': status_form,
        'comment_form': comment_form,
    }
    return render(request, 'repairs/request_detail.html', context)


@tenant_required
def request_edit(request, pk):
    profile = request.user.profile
    repair = get_object_or_404(RepairRequest, pk=pk, tenant=profile)

    if not repair.can_edit:
        messages.error(request, 'You can only edit pending requests.')
        return redirect('request_detail', pk=pk)

    if request.method == 'POST':
        form = RepairRequestForm(request.POST, request.FILES, instance=repair)
        if form.is_valid():
            form.save()
            messages.success(request, 'Request updated successfully.')
            return redirect('request_detail', pk=pk)
    else:
        form = RepairRequestForm(instance=repair)
    return render(request, 'repairs/request_edit.html', {
        'form': form, 'repair': repair,
    })


@tenant_required
def request_delete(request, pk):
    profile = request.user.profile
    repair = get_object_or_404(RepairRequest, pk=pk, tenant=profile)

    if not repair.can_edit:
        messages.error(request, 'You can only delete pending requests.')
        return redirect('request_detail', pk=pk)

    if request.method == 'POST':
        repair.delete()
        messages.success(request, 'Request deleted.')
        return redirect('request_list')
    return render(request, 'repairs/request_delete_confirm.html', {
        'repair': repair,
    })


@login_required_with_message
def request_list(request):
    profile = request.user.profile
    filter_form = RequestFilterForm(request.GET)

    if profile.is_staff_member:
        queryset = RepairRequest.objects.select_related(
            'tenant__user', 'dwelling__community'
        ).all()
    else:
        queryset = RepairRequest.objects.filter(
            tenant=profile
        ).select_related('dwelling__community')

    # Apply filters from GET params
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            queryset = queryset.filter(
                status=filter_form.cleaned_data['status']
            )
        if filter_form.cleaned_data.get('issue_type'):
            queryset = queryset.filter(
                issue_type=filter_form.cleaned_data['issue_type']
            )
        if filter_form.cleaned_data.get('priority'):
            queryset = queryset.filter(
                priority=filter_form.cleaned_data['priority']
            )

    # Search (staff only)
    search_query = request.GET.get('q', '').strip()
    if search_query and profile.is_staff_member:
        queryset = queryset.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(tenant__user__first_name__icontains=search_query) |
            Q(tenant__user__last_name__icontains=search_query) |
            Q(dwelling__address__icontains=search_query) |
            Q(dwelling__community__name__icontains=search_query)
        )

    paginator = Paginator(queryset, 10)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)

    context = {
        'requests': requests_page,
        'filter_form': filter_form,
        'is_staff': profile.is_staff_member,
        'search_query': search_query,
    }
    return render(request, 'repairs/request_list.html', context)


# ── Tenant Comment ───────────────────────────────────────────────

@tenant_required
def add_comment(request, pk):
    """Allow tenants to add comments/notes on their own requests."""
    profile = request.user.profile
    repair = get_object_or_404(RepairRequest, pk=pk, tenant=profile)

    if request.method == 'POST':
        form = TenantCommentForm(request.POST)
        if form.is_valid():
            MaintenanceLog.objects.create(
                repair_request=repair,
                author=profile,
                note=form.cleaned_data['comment'],
            )
            messages.success(request, 'Comment added.')
    return redirect('request_detail', pk=pk)


# ── Staff Actions ────────────────────────────────────────────────

@staff_required
def update_request_status(request, pk):
    repair = get_object_or_404(RepairRequest, pk=pk)
    staff_profile = request.user.profile

    if request.method == 'POST':
        # Handle status update
        status_form = StatusUpdateForm(request.POST)
        if status_form.is_valid():
            new_status = status_form.cleaned_data['status']
            old_status = repair.get_status_display()

            if new_status == 'IN_REVIEW':
                repair.mark_in_review()
            elif new_status == 'IN_PROGRESS':
                repair.mark_in_progress(staff_profile)
            elif new_status == 'COMPLETED':
                repair.mark_completed()
            elif new_status == 'CANCELLED':
                repair.cancel()
            else:
                repair.status = new_status
                repair.save()

            # Auto-create a maintenance log for status change
            MaintenanceLog.objects.create(
                repair_request=repair,
                author=staff_profile,
                note=f'Status changed from {old_status} to {repair.get_status_display()}',
                status_change=new_status,
            )
            messages.success(
                request,
                f'Status updated to {repair.get_status_display()}.'
            )

        # Handle maintenance log note
        log_form = MaintenanceLogForm(request.POST)
        if log_form.is_valid() and log_form.cleaned_data.get('note'):
            log = log_form.save(commit=False)
            log.repair_request = repair
            log.author = staff_profile
            log.save()
            messages.success(request, 'Maintenance note added.')

    return redirect('request_detail', pk=pk)


# ── Dwelling ─────────────────────────────────────────────────────

@login_required_with_message
def dwelling_detail(request, pk):
    dwelling = get_object_or_404(
        Dwelling.objects.select_related('community'),
        pk=pk
    )

    # Security: tenants can only view their own dwelling
    profile = request.user.profile
    if profile.is_tenant and profile.dwelling != dwelling:
        messages.error(request, 'You can only view your own dwelling.')
        return redirect('tenant_dashboard')

    maintenance_history = dwelling.maintenance_history()
    active_requests = dwelling.repair_requests.active().select_related('tenant__user')

    context = {
        'dwelling': dwelling,
        'maintenance_history': maintenance_history,
        'active_requests': active_requests,
        'tenant_count': dwelling.tenants.count(),
    }
    return render(request, 'dwelling/dwelling_detail.html', context)


# ── Profile & Password ─────────────────────────────────────

@login_required_with_message
def profile_view(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, user=request.user)
        if form.is_valid():
            form.save(request.user)
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = ProfileEditForm(user=request.user)
    return render(request, 'auth/profile.html', {'form': form})


@login_required_with_message
def password_change_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'auth/password_change.html', {'form': form})


# ── Communities & Dwellings (Staff) ─────────────────────────

@staff_required
def community_list(request):
    communities = Community.objects.annotate(
        num_dwellings=Count('dwellings'),
        num_active_requests=Count(
            'dwellings__repair_requests',
            filter=~Q(dwellings__repair_requests__status__in=['COMPLETED', 'CANCELLED'])
        ),
    ).order_by('name')
    paginator = Paginator(communities, 12)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'communities/community_list.html', {'communities': page})


@staff_required
def community_detail(request, pk):
    community = get_object_or_404(Community, pk=pk)
    dwellings = community.dwellings.annotate(
        num_active_requests=Count(
            'repair_requests',
            filter=~Q(repair_requests__status__in=['COMPLETED', 'CANCELLED'])
        ),
    )
    context = {
        'community': community,
        'dwellings': dwellings,
        'total_requests': RepairRequest.objects.filter(
            dwelling__community=community
        ).count(),
        'active_requests': RepairRequest.objects.filter(
            dwelling__community=community
        ).active().count(),
    }
    return render(request, 'communities/community_detail.html', context)


@staff_required
def dwelling_list(request):
    queryset = Dwelling.objects.select_related('community').annotate(
        num_active_requests=Count(
            'repair_requests',
            filter=~Q(repair_requests__status__in=['COMPLETED', 'CANCELLED'])
        ),
    ).order_by('community__name', 'address')
    community_filter = request.GET.get('community')
    if community_filter:
        queryset = queryset.filter(community_id=community_filter)

    paginator = Paginator(queryset, 15)
    page = paginator.get_page(request.GET.get('page'))
    context = {
        'dwellings': page,
        'communities': Community.objects.all(),
        'selected_community': community_filter,
    }
    return render(request, 'dwelling/dwelling_list.html', context)


# ── Analytics & Export (Staff) ──────────────────────────────

@staff_required
def analytics_view(request):
    all_requests = RepairRequest.objects.all()
    completed = all_requests.completed()

    avg_days = None
    if completed.exists():
        completed_with_days = completed.exclude(completed_at__isnull=True)
        if completed_with_days.exists():
            avg_seconds = completed_with_days.aggregate(
                avg_duration=Avg(F('completed_at') - F('created_at'))
            )['avg_duration']
            if avg_seconds:
                avg_days = avg_seconds.days

    six_months_ago = timezone.now() - timezone.timedelta(days=180)
    monthly_stats = (
        all_requests.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    context = {
        'total_requests': all_requests.count(),
        'pending_count': all_requests.pending().count(),
        'in_progress_count': all_requests.in_progress().count(),
        'completed_count': completed.count(),
        'overdue_count': all_requests.overdue().count(),
        'avg_completion_days': avg_days,
        'stats_by_issue': all_requests.stats_by_issue_type(),
        'stats_by_community': all_requests.stats_by_community(),
        'stats_by_status': all_requests.stats_by_status(),
        'stats_by_priority': all_requests.stats_by_priority(),
        'monthly_stats': monthly_stats,
        'avg_rating': RepairFeedback.objects.aggregate(
            avg=Avg('rating')
        )['avg'],
        'total_feedback': RepairFeedback.objects.count(),
    }
    return render(request, 'analytics/analytics.html', context)


@staff_required
def export_csv(request):
    """Export repair requests as a CSV download."""
    queryset = RepairRequest.objects.select_related(
        'tenant__user', 'dwelling__community', 'assigned_to__user'
    ).all()

    # Apply filters if provided
    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(status=status)
    issue_type = request.GET.get('issue_type')
    if issue_type:
        queryset = queryset.filter(issue_type=issue_type)

    class Echo:
        def write(self, value):
            return value

    def rows():
        yield [
            'ID', 'Title', 'Tenant', 'Community', 'Dwelling',
            'Issue Type', 'Priority', 'Status', 'Location',
            'Created', 'Completed', 'Days Open', 'Assigned To'
        ]
        for r in queryset.iterator():
            yield [
                r.pk, r.title, r.tenant.full_name,
                r.dwelling.community.name, r.dwelling.address,
                r.get_issue_type_display(), r.get_priority_display(),
                r.get_status_display(), r.get_location_in_dwelling_display(),
                r.created_at.strftime('%Y-%m-%d'),
                r.completed_at.strftime('%Y-%m-%d') if r.completed_at else '',
                r.days_open,
                r.assigned_to.full_name if r.assigned_to else '',
            ]

    writer = csv.writer(Echo())
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in rows()),
        content_type='text/csv',
    )
    response['Content-Disposition'] = 'attachment; filename="repair_requests.csv"'
    return response


# ── Feedback (Tenant) ──────────────────────────────────────

@tenant_required
def submit_feedback(request, pk):
    profile = request.user.profile
    repair = get_object_or_404(RepairRequest, pk=pk, tenant=profile)

    if repair.status != 'COMPLETED':
        messages.error(request, 'You can only leave feedback on completed repairs.')
        return redirect('request_detail', pk=pk)

    if hasattr(repair, 'feedback'):
        messages.info(request, 'You have already submitted feedback for this repair.')
        return redirect('request_detail', pk=pk)

    if request.method == 'POST':
        form = RepairFeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.repair_request = repair
            feedback.tenant = profile
            feedback.save()
            if repair.assigned_to:
                Notification.objects.create(
                    recipient=repair.assigned_to,
                    title=f'Feedback received for "{repair.title}"',
                    message=f'{profile.full_name} rated the repair {feedback.rating}/5.',
                    notification_type='FEEDBACK_RECEIVED',
                    related_request=repair,
                )
            messages.success(request, 'Thank you for your feedback!')
            return redirect('request_detail', pk=pk)
    else:
        form = RepairFeedbackForm()
    return render(request, 'repairs/submit_feedback.html', {
        'form': form, 'repair': repair,
    })


# ── Cancel Request (Tenant) ────────────────────────────────

@tenant_required
def cancel_request(request, pk):
    profile = request.user.profile
    repair = get_object_or_404(RepairRequest, pk=pk, tenant=profile)

    if not repair.is_active:
        messages.error(request, 'This request is already closed.')
        return redirect('request_detail', pk=pk)

    if request.method == 'POST':
        repair.cancel()
        MaintenanceLog.objects.create(
            repair_request=repair,
            author=profile,
            note='Request cancelled by tenant.',
            status_change='CANCELLED',
        )
        messages.success(request, 'Request cancelled.')
        return redirect('request_list')
    return render(request, 'repairs/cancel_confirm.html', {'repair': repair})


# ── Notifications ──────────────────────────────────────────

@login_required_with_message
def notification_list(request):
    profile = request.user.profile
    notifications = Notification.objects.filter(
        recipient=profile
    ).select_related('related_request')
    paginator = Paginator(notifications, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'notifications/notification_list.html', {
        'notifications': page,
    })


@login_required_with_message
def mark_notification_read(request, pk):
    profile = request.user.profile
    notification = get_object_or_404(Notification, pk=pk, recipient=profile)
    notification.mark_read()
    if notification.related_request:
        return redirect('request_detail', pk=notification.related_request.pk)
    return redirect('notification_list')


@login_required_with_message
def mark_all_notifications_read(request):
    if request.method == 'POST':
        profile = request.user.profile
        Notification.objects.filter(
            recipient=profile, is_read=False
        ).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')


# ── Error Pages ────────────────────────────────────────────

def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)
