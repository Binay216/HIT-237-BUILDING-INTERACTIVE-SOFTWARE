from django.db import models
from django.utils import timezone
from datetime import timedelta


class RepairRequestQuerySet(models.QuerySet):
    """Custom QuerySet for RepairRequest with common filters and aggregations."""

    def pending(self):
        return self.filter(status='PENDING')

    def in_review(self):
        return self.filter(status='IN_REVIEW')

    def in_progress(self):
        return self.filter(status='IN_PROGRESS')

    def completed(self):
        return self.filter(status='COMPLETED')

    def cancelled(self):
        return self.filter(status='CANCELLED')

    def active(self):
        """All requests that are not completed or cancelled."""
        return self.exclude(status__in=['COMPLETED', 'CANCELLED'])

    def by_priority(self, priority):
        return self.filter(priority=priority)

    def by_issue_type(self, issue_type):
        return self.filter(issue_type=issue_type)

    def overdue(self, days=14):
        """Requests pending longer than the given number of days."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(status='PENDING', created_at__lte=cutoff)

    def for_community(self, community):
        return self.filter(dwelling__community=community)

    def for_dwelling(self, dwelling):
        return self.filter(dwelling=dwelling)

    def stats_by_issue_type(self):
        """Aggregate count of requests grouped by issue type."""
        return (
            self.values('issue_type')
            .annotate(count=models.Count('id'))
            .order_by('-count')
        )

    def stats_by_community(self):
        """Aggregate count of requests grouped by community."""
        return (
            self.values('dwelling__community__name')
            .annotate(count=models.Count('id'))
            .order_by('-count')
        )

    def stats_by_status(self):
        """Aggregate count of requests grouped by status."""
        return (
            self.values('status')
            .annotate(count=models.Count('id'))
            .order_by('status')
        )

    def stats_by_priority(self):
        """Aggregate count of requests grouped by priority."""
        return (
            self.values('priority')
            .annotate(count=models.Count('id'))
            .order_by('priority')
        )

    def recent(self, limit=10):
        return self.order_by('-created_at')[:limit]


class RepairRequestManager(models.Manager):
    """Custom manager that uses RepairRequestQuerySet."""

    def get_queryset(self):
        return RepairRequestQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending()

    def in_progress(self):
        return self.get_queryset().in_progress()

    def completed(self):
        return self.get_queryset().completed()

    def active(self):
        return self.get_queryset().active()

    def overdue(self, days=14):
        return self.get_queryset().overdue(days)

    def stats_by_issue_type(self):
        return self.get_queryset().stats_by_issue_type()

    def stats_by_community(self):
        return self.get_queryset().stats_by_community()

    def stats_by_status(self):
        return self.get_queryset().stats_by_status()
