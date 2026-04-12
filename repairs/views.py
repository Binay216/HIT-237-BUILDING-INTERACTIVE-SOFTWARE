import csv

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Q, Count, Avg, F
from django.db.models.functions import TruncMonth
from django.http import StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView,
)

from .models import (
    RepairRequest, Dwelling, MaintenanceLog, Community,
    Notification, RepairFeedback
)
from .forms import (
    RegistrationForm, RepairRequestForm, MaintenanceLogForm,
    StatusUpdateForm, RequestFilterForm, TenantCommentForm,
    ProfileEditForm, RepairFeedbackForm
)
from .mixins import (
    LoginRequiredWithMessageMixin, StaffRequiredMixin, TenantRequiredMixin,
)
from .decorators import login_required_with_message, tenant_required, staff_required


# ════════════════════════════════════════════════════════════════
#  Function-Based Views (auth, simple actions)
# ════════════════════════════════════════════════════════════════

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


# ── Dashboard Redirect ──────────────────────────────────────────

@login_required_with_message
def dashboard_redirect(request):
    """Redirect to the appropriate dashboard based on user role."""
    if hasattr(request.user, 'profile') and request.user.profile.is_staff_member:
        return redirect('staff_dashboard')
    return redirect('tenant_dashboard')


# ── Staff Actions (POST-only) ──────────────────────────────────

@staff_required
def update_request_status(request, pk):
    repair = get_object_or_404(RepairRequest, pk=pk)
    staff_profile = request.user.profile

    if request.method == 'POST':
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

        log_form = MaintenanceLogForm(request.POST)
        if log_form.is_valid() and log_form.cleaned_data.get('note'):
            log = log_form.save(commit=False)
            log.repair_request = repair
            log.author = staff_profile
            log.save()
            messages.success(request, 'Maintenance note added.')

    return redirect('request_detail', pk=pk)


# ── Tenant Comment ──────────────────────────────────────────────

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


# ── Feedback (Tenant) ──────────────────────────────────────────

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


# ── Cancel Request (Tenant) ────────────────────────────────────

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


# ── Notification Actions ────────────────────────────────────────

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


# ── Profile & Password ─────────────────────────────────────────

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


# ── CSV Export (Streaming) ──────────────────────────────────────

@staff_required
def export_csv(request):
    """Export repair requests as a CSV download using streaming response."""
    queryset = RepairRequest.objects.select_related(
        'tenant__user', 'dwelling__community', 'assigned_to__user'
    ).all()

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


# ── Error Pages ─────────────────────────────────────────────────

def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)


# ════════════════════════════════════════════════════════════════
#  Class-Based Views
# ════════════════════════════════════════════════════════════════

# ── Dashboards ──────────────────────────────────────────────────

class TenantDashboardView(TenantRequiredMixin, TemplateView):
    """Dashboard for tenants showing their requests and dwelling info."""

    template_name = 'dashboard/tenant_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        overdue_requests = RepairRequest.objects.filter(
            tenant=profile
        ).active()
        overdue_list = [r for r in overdue_requests if r.is_overdue()]

        context.update({
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
        })
        return context


class StaffDashboardView(StaffRequiredMixin, TemplateView):
    """Dashboard for maintenance staff with aggregate statistics."""

    template_name = 'dashboard/staff_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
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
        })
        return context


# ── Repair Request CRUD ─────────────────────────────────────────

class RepairRequestListView(LoginRequiredWithMessageMixin, ListView):
    """
    Paginated list of repair requests with role-based filtering.
    Staff see all requests with search; tenants see only their own.
    """

    model = RepairRequest
    template_name = 'repairs/request_list.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        profile = self.request.user.profile

        if profile.is_staff_member:
            queryset = RepairRequest.objects.select_related(
                'tenant__user', 'dwelling__community'
            ).all()
        else:
            queryset = RepairRequest.objects.filter(
                tenant=profile
            ).select_related('dwelling__community')

        # Apply filters from GET params
        self.filter_form = RequestFilterForm(self.request.GET)
        if self.filter_form.is_valid():
            if self.filter_form.cleaned_data.get('status'):
                queryset = queryset.filter(
                    status=self.filter_form.cleaned_data['status']
                )
            if self.filter_form.cleaned_data.get('issue_type'):
                queryset = queryset.filter(
                    issue_type=self.filter_form.cleaned_data['issue_type']
                )
            if self.filter_form.cleaned_data.get('priority'):
                queryset = queryset.filter(
                    priority=self.filter_form.cleaned_data['priority']
                )

        # Search (staff only)
        self.search_query = self.request.GET.get('q', '').strip()
        if self.search_query and profile.is_staff_member:
            queryset = queryset.filter(
                Q(title__icontains=self.search_query) |
                Q(description__icontains=self.search_query) |
                Q(tenant__user__first_name__icontains=self.search_query) |
                Q(tenant__user__last_name__icontains=self.search_query) |
                Q(dwelling__address__icontains=self.search_query) |
                Q(dwelling__community__name__icontains=self.search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['is_staff'] = self.request.user.profile.is_staff_member
        context['search_query'] = self.search_query
        return context


class RepairRequestCreateView(TenantRequiredMixin, CreateView):
    """Allows tenants to submit a new repair request for their dwelling."""

    model = RepairRequest
    form_class = RepairRequestForm
    template_name = 'repairs/request_create.html'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            if not request.user.profile.dwelling:
                messages.error(
                    request,
                    'You need to be assigned to a dwelling before submitting '
                    'requests. Please contact your housing coordinator.'
                )
                return redirect('tenant_dashboard')
        return response

    def form_valid(self, form):
        profile = self.request.user.profile
        form.instance.tenant = profile
        form.instance.dwelling = profile.dwelling
        messages.success(self.request, 'Repair request submitted successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class RepairRequestDetailView(LoginRequiredWithMessageMixin, DetailView):
    """
    Full detail page for a repair request.
    Tenants see their own requests only; staff see all.
    Provides role-appropriate forms in context.
    """

    model = RepairRequest
    template_name = 'repairs/request_detail.html'
    context_object_name = 'repair'

    def get_queryset(self):
        return RepairRequest.objects.select_related(
            'tenant__user', 'dwelling__community', 'assigned_to__user'
        )

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(self, 'object') and self.object:
            profile = request.user.profile
            if profile.is_tenant and self.object.tenant != profile:
                messages.error(request, 'You can only view your own requests.')
                return redirect('request_list')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        repair = self.object

        context['logs'] = repair.logs.select_related('author__user').all()

        if profile.is_staff_member:
            context['log_form'] = MaintenanceLogForm()
            context['status_form'] = StatusUpdateForm(
                initial={'status': repair.status}
            )
        elif profile.is_tenant and repair.is_active:
            context['comment_form'] = TenantCommentForm()

        return context


class RepairRequestUpdateView(TenantRequiredMixin, UpdateView):
    """Allows tenants to edit their own pending repair requests."""

    model = RepairRequest
    form_class = RepairRequestForm
    template_name = 'repairs/request_edit.html'
    context_object_name = 'repair'

    def get_queryset(self):
        return RepairRequest.objects.filter(
            tenant=self.request.user.profile
        )

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(self, 'object') and self.object and not self.object.can_edit:
            messages.error(request, 'You can only edit pending requests.')
            return redirect('request_detail', pk=self.object.pk)
        return response

    def form_valid(self, form):
        messages.success(self.request, 'Request updated successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class RepairRequestDeleteView(TenantRequiredMixin, DeleteView):
    """Allows tenants to delete their own pending repair requests."""

    model = RepairRequest
    template_name = 'repairs/request_delete_confirm.html'
    context_object_name = 'repair'
    success_url = reverse_lazy('request_list')

    def get_queryset(self):
        return RepairRequest.objects.filter(
            tenant=self.request.user.profile
        )

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.can_edit:
            messages.error(request, 'You can only delete pending requests.')
            return redirect('request_detail', pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Request deleted.')
        return super().form_valid(form)


# ── Community & Dwelling Views ──────────────────────────────────

class CommunityListView(StaffRequiredMixin, ListView):
    """Paginated list of all NT remote communities (staff only)."""

    model = Community
    template_name = 'communities/community_list.html'
    context_object_name = 'communities'
    paginate_by = 12

    def get_queryset(self):
        return Community.objects.annotate(
            num_dwellings=Count('dwellings'),
            num_active_requests=Count(
                'dwellings__repair_requests',
                filter=~Q(dwellings__repair_requests__status__in=[
                    'COMPLETED', 'CANCELLED'
                ])
            ),
        ).order_by('name')


class CommunityDetailView(StaffRequiredMixin, DetailView):
    """Detail view for a single community with its dwellings (staff only)."""

    model = Community
    template_name = 'communities/community_detail.html'
    context_object_name = 'community'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        community = self.object
        context['dwellings'] = community.dwellings.annotate(
            num_active_requests=Count(
                'repair_requests',
                filter=~Q(repair_requests__status__in=[
                    'COMPLETED', 'CANCELLED'
                ])
            ),
        )
        context['total_requests'] = RepairRequest.objects.filter(
            dwelling__community=community
        ).count()
        context['active_requests'] = RepairRequest.objects.filter(
            dwelling__community=community
        ).active().count()
        return context


class DwellingListView(StaffRequiredMixin, ListView):
    """Paginated list of all dwellings, filterable by community (staff only)."""

    model = Dwelling
    template_name = 'dwelling/dwelling_list.html'
    context_object_name = 'dwellings'
    paginate_by = 15

    def get_queryset(self):
        queryset = Dwelling.objects.select_related('community').annotate(
            num_active_requests=Count(
                'repair_requests',
                filter=~Q(repair_requests__status__in=[
                    'COMPLETED', 'CANCELLED'
                ])
            ),
        ).order_by('community__name', 'address')

        community_filter = self.request.GET.get('community')
        if community_filter:
            queryset = queryset.filter(community_id=community_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['communities'] = Community.objects.all()
        context['selected_community'] = self.request.GET.get('community')
        return context


class DwellingDetailView(LoginRequiredWithMessageMixin, DetailView):
    """
    Detail view for a single dwelling.
    Tenants can only view their own dwelling; staff can view any.
    """

    model = Dwelling
    template_name = 'dwelling/dwelling_detail.html'
    context_object_name = 'dwelling'

    def get_queryset(self):
        return Dwelling.objects.select_related('community')

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(self, 'object') and self.object:
            profile = request.user.profile
            if profile.is_tenant and profile.dwelling != self.object:
                messages.error(request, 'You can only view your own dwelling.')
                return redirect('tenant_dashboard')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dwelling = self.object
        context['maintenance_history'] = dwelling.maintenance_history()
        context['active_requests'] = dwelling.repair_requests.active().select_related(
            'tenant__user'
        )
        context['tenant_count'] = dwelling.tenants.count()
        return context


# ── Notifications ───────────────────────────────────────────────

class NotificationListView(LoginRequiredWithMessageMixin, ListView):
    """Paginated list of notifications for the current user."""

    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user.profile
        ).select_related('related_request')


# ── Analytics ───────────────────────────────────────────────────

class AnalyticsView(StaffRequiredMixin, TemplateView):
    """Comprehensive analytics dashboard for staff with aggregate statistics."""

    template_name = 'analytics/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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

        context.update({
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
        })
        return context
