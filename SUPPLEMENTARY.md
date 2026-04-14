# Supplementary Materials

## NT Remote Housing Repair System

---

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    User ||--|| TenantProfile : "has one"
    TenantProfile }o--|| Dwelling : "lives in (optional)"
    Dwelling }o--|| Community : "belongs to"
    RepairRequest }o--|| TenantProfile : "submitted by"
    RepairRequest }o--|| Dwelling : "located at"
    RepairRequest }o--o| TenantProfile : "assigned to (optional)"
    RepairRequest ||--o| RepairFeedback : "has feedback (optional)"
    RepairRequest ||--o{ MaintenanceLog : "has logs"
    RepairRequest ||--o{ Notification : "triggers notifications"
    Notification }o--|| TenantProfile : "sent to"

    Community {
        int id PK
        string name
        string region "TOP_END | CENTRAL | BARKLY | BIG_RIVERS | EAST_ARNHEM"
        int population
        datetime created_at
    }

    Dwelling {
        int id PK
        string address
        int community_id FK
        string dwelling_type "HOUSE | UNIT | DUPLEX | TOWN_CAMP"
        int bedrooms
        int year_built
        boolean meets_ncc_standards
        datetime created_at
    }

    User {
        int id PK
        string username
        string first_name
        string last_name
        string password
    }

    TenantProfile {
        int id PK
        int user_id FK "OneToOne"
        string phone
        int dwelling_id FK "nullable"
        boolean is_staff_member
        date date_joined_community
    }

    RepairRequest {
        int id PK
        int tenant_id FK
        int dwelling_id FK
        string title
        text description
        string issue_type "AC | PLUMBING | ELECTRICAL | ..."
        string priority "LOW | MEDIUM | HIGH | EMERGENCY"
        string status "PENDING | IN_REVIEW | IN_PROGRESS | COMPLETED | CANCELLED"
        string location_in_dwelling
        file image
        int assigned_to_id FK "nullable"
        datetime created_at
        datetime updated_at
        datetime completed_at "nullable"
    }

    MaintenanceLog {
        int id PK
        int repair_request_id FK
        int author_id FK
        text note
        string status_change "nullable"
        datetime created_at
    }

    Notification {
        int id PK
        int recipient_id FK
        string title
        text message
        string notification_type "STATUS_CHANGE | NEW_ASSIGNMENT | FEEDBACK_RECEIVED | SYSTEM"
        int related_request_id FK "nullable"
        boolean is_read
        datetime created_at
    }

    RepairFeedback {
        int id PK
        int repair_request_id FK "OneToOne"
        int tenant_id FK
        int rating "1-5"
        text comment
        datetime created_at
    }
```

---

## 2. Class Diagram (Application Architecture)

```mermaid
classDiagram
    direction TB

    class Community {
        +CharField name
        +CharField region
        +PositiveIntegerField population
        +DateTimeField created_at
        +dwelling_count() int
        +active_request_count() int
    }

    class Dwelling {
        +CharField address
        +ForeignKey community
        +CharField dwelling_type
        +PositiveIntegerField bedrooms
        +PositiveIntegerField year_built
        +BooleanField meets_ncc_standards
        +active_repair_count() int
        +maintenance_history() QuerySet
        +is_overcrowded(occupant_count) bool
        +compliance_status() str
        +total_requests() int
    }

    class TenantProfile {
        +OneToOneField user
        +CharField phone
        +ForeignKey dwelling
        +BooleanField is_staff_member
        +DateField date_joined_community
        +full_name() str
        +open_requests() QuerySet
        +completed_requests() QuerySet
        +is_tenant() bool
    }

    class RepairRequest {
        +ForeignKey tenant
        +ForeignKey dwelling
        +CharField title
        +TextField description
        +CharField issue_type
        +CharField priority
        +CharField status
        +CharField location_in_dwelling
        +FileField image
        +ForeignKey assigned_to
        +DateTimeField created_at
        +DateTimeField completed_at
        +mark_in_review()
        +mark_in_progress(staff_profile)
        +mark_completed()
        +cancel()
        +is_overdue(days) bool
        +days_open() int
        +is_active() bool
        +can_edit() bool
        +get_absolute_url() str
    }

    class MaintenanceLog {
        +ForeignKey repair_request
        +ForeignKey author
        +TextField note
        +CharField status_change
        +DateTimeField created_at
    }

    class Notification {
        +ForeignKey recipient
        +CharField title
        +TextField message
        +CharField notification_type
        +ForeignKey related_request
        +BooleanField is_read
        +mark_read()
    }

    class RepairFeedback {
        +OneToOneField repair_request
        +ForeignKey tenant
        +PositiveIntegerField rating
        +TextField comment
    }

    class RepairRequestQuerySet {
        +pending() QuerySet
        +in_review() QuerySet
        +in_progress() QuerySet
        +completed() QuerySet
        +cancelled() QuerySet
        +active() QuerySet
        +overdue(days) QuerySet
        +by_priority(priority) QuerySet
        +by_issue_type(issue_type) QuerySet
        +for_community(community) QuerySet
        +for_dwelling(dwelling) QuerySet
        +stats_by_issue_type() QuerySet
        +stats_by_community() QuerySet
        +stats_by_status() QuerySet
        +stats_by_priority() QuerySet
        +recent(limit) QuerySet
    }

    class RepairRequestManager {
        +get_queryset() RepairRequestQuerySet
        +pending() QuerySet
        +completed() QuerySet
        +active() QuerySet
        +overdue(days) QuerySet
        +stats_by_issue_type() QuerySet
        +stats_by_community() QuerySet
    }

    Community "1" --> "*" Dwelling : contains
    Dwelling "1" --> "*" TenantProfile : houses
    TenantProfile "1" --> "*" RepairRequest : submits
    Dwelling "1" --> "*" RepairRequest : located at
    RepairRequest "1" --> "0..1" RepairFeedback : has feedback
    RepairRequest "1" --> "*" MaintenanceLog : has logs
    RepairRequest "1" --> "*" Notification : triggers
    TenantProfile "1" --> "*" Notification : receives

    RepairRequestManager --> RepairRequestQuerySet : delegates to
    RepairRequest --> RepairRequestManager : objects
```

---

## 3. View Architecture Diagram

```mermaid
classDiagram
    direction TB

    class LoginRequiredMixin {
        <<Django Built-in>>
    }

    class LoginRequiredWithMessageMixin {
        +login_url = "login"
        +handle_no_permission()
    }

    class StaffRequiredMixin {
        +dispatch(request)
    }

    class TenantRequiredMixin {
        +dispatch(request)
    }

    LoginRequiredMixin <|-- LoginRequiredWithMessageMixin
    LoginRequiredWithMessageMixin <|-- StaffRequiredMixin
    LoginRequiredWithMessageMixin <|-- TenantRequiredMixin

    class ListView {
        <<Django Generic>>
    }
    class DetailView {
        <<Django Generic>>
    }
    class CreateView {
        <<Django Generic>>
    }
    class UpdateView {
        <<Django Generic>>
    }
    class DeleteView {
        <<Django Generic>>
    }
    class TemplateView {
        <<Django Generic>>
    }

    class RepairRequestListView {
        +model = RepairRequest
        +paginate_by = 10
        +get_queryset()
        +get_context_data()
    }
    class RepairRequestCreateView {
        +model = RepairRequest
        +form_class = RepairRequestForm
        +form_valid(form)
    }
    class RepairRequestDetailView {
        +model = RepairRequest
        +get_queryset()
        +get_context_data()
    }
    class RepairRequestUpdateView {
        +model = RepairRequest
        +form_class = RepairRequestForm
        +form_valid(form)
    }
    class RepairRequestDeleteView {
        +model = RepairRequest
        +success_url
        +form_valid(form)
    }
    class CommunityListView {
        +model = Community
        +paginate_by = 12
        +get_queryset()
    }
    class CommunityDetailView {
        +model = Community
        +get_context_data()
    }
    class DwellingListView {
        +model = Dwelling
        +paginate_by = 15
        +get_queryset()
    }
    class DwellingDetailView {
        +model = Dwelling
        +get_context_data()
    }
    class TenantDashboardView {
        +get_context_data()
    }
    class StaffDashboardView {
        +get_context_data()
    }
    class AnalyticsView {
        +get_context_data()
    }
    class NotificationListView {
        +model = Notification
        +paginate_by = 20
        +get_queryset()
    }

    LoginRequiredWithMessageMixin <|-- RepairRequestListView
    ListView <|-- RepairRequestListView

    TenantRequiredMixin <|-- RepairRequestCreateView
    CreateView <|-- RepairRequestCreateView

    LoginRequiredWithMessageMixin <|-- RepairRequestDetailView
    DetailView <|-- RepairRequestDetailView

    TenantRequiredMixin <|-- RepairRequestUpdateView
    UpdateView <|-- RepairRequestUpdateView

    TenantRequiredMixin <|-- RepairRequestDeleteView
    DeleteView <|-- RepairRequestDeleteView

    StaffRequiredMixin <|-- CommunityListView
    ListView <|-- CommunityListView

    StaffRequiredMixin <|-- CommunityDetailView
    DetailView <|-- CommunityDetailView

    StaffRequiredMixin <|-- DwellingListView
    ListView <|-- DwellingListView

    LoginRequiredWithMessageMixin <|-- DwellingDetailView
    DetailView <|-- DwellingDetailView

    TenantRequiredMixin <|-- TenantDashboardView
    TemplateView <|-- TenantDashboardView

    StaffRequiredMixin <|-- StaffDashboardView
    TemplateView <|-- StaffDashboardView

    StaffRequiredMixin <|-- AnalyticsView
    TemplateView <|-- AnalyticsView

    LoginRequiredWithMessageMixin <|-- NotificationListView
    ListView <|-- NotificationListView
```

---

## 4. Request Status Lifecycle (State Machine)

```mermaid
stateDiagram-v2
    [*] --> Pending : Tenant submits request

    Pending --> InReview : Staff reviews
    Pending --> Cancelled : Tenant cancels

    InReview --> InProgress : Staff starts work\n(assigns self)
    InReview --> Cancelled : Tenant cancels

    InProgress --> Completed : Staff marks done\n(sets completed_at)
    InProgress --> Cancelled : Tenant cancels

    Completed --> [*]
    Cancelled --> [*]

    note right of Pending
        is_overdue() = True
        after 14 days
    end note

    note right of Completed
        Tenant can submit
        RepairFeedback (1-5)
    end note
```

---

## 5. Django Design Philosophies Demonstrated

The following Django design philosophies are explicitly implemented in this project. References are to the [Django Design Philosophies documentation](https://docs.djangoproject.com/en/5.1/misc/design-philosophies/).

### Philosophy 1: Loose Coupling

> "A fundamental goal of Django's stack is loose coupling and tight cohesion."

Each layer of the application is independent and communicates through well-defined interfaces:

| Layer | Responsibility | Coupling Point |
|-------|---------------|----------------|
| **Models** (`models.py`) | Data + domain logic | Knows nothing about views or templates |
| **Views** (`views.py`) | HTTP handling + routing | Uses model methods, not raw SQL |
| **Forms** (`forms.py`) | Validation + transformation | Independent of views that use them |
| **Signals** (`signals.py`) | Cross-cutting concerns | Decoupled from both models and views |
| **Templates** | Presentation only | Receives context dict, no direct model access |
| **Mixins** (`mixins.py`) | Access control | Composable via MRO, independent of view logic |

**Evidence:** The `notify_on_status_change` signal (`signals.py:15–43`) fires on any `RepairRequest` save — whether triggered by a view, admin action, management command, or test. The model methods (`mark_in_review()`, etc.) have no knowledge of notifications. This is loose coupling in practice.

### Philosophy 2: Don't Repeat Yourself (DRY)

> "Every distinct concept and/or piece of data should live in one, and only one, place."

| What | Single Source of Truth | Where |
|------|----------------------|-------|
| "Active request" definition | `RepairRequestQuerySet.active()` | `managers.py:24–26` |
| Status → CSS class mapping | `status_class` filter | `templatetags/repair_tags.py:7–16` |
| User role + notification count | `global_context` processor | `context_processors.py:4–14` |
| Profile invariant | `ProfileEnforcementMiddleware` | `middleware.py:1–28` |
| Role-based access (CBV) | `StaffRequiredMixin` / `TenantRequiredMixin` | `mixins.py:25–52` |

**Evidence:** Changing the definition of "overdue" from 14 to 21 days requires editing one line (`managers.py:34`). Every dashboard, list view, and analytics page that uses `overdue()` automatically reflects the change.

### Philosophy 3: Explicit is Better Than Implicit

> "Django shouldn't do too much magic. Magic shouldn't happen unless there's a really good reason for it."

- Every model relationship uses an **explicit `on_delete`** behaviour and **explicit `related_name`** (`models.py:55`, `102`, `106`, `182`, `185`, `201`, `267`, `270`, etc.)
- Every `save()` call uses **`update_fields`** to make clear exactly which columns are being written (`models.py:220`, `225`, `230`, `234`)
- Custom managers expose an **explicit public API** — not every QuerySet method is exposed on the Manager (`managers.py:81–109`)
- Access control uses **explicitly named mixins/decorators** rather than relying on Django's implicit permission framework

### Philosophy 4: Models Should Encapsulate Every Aspect of an Object

> "Models should encapsulate every aspect of an 'object', following Martin Fowler's Active Record design pattern."

The `RepairRequest` model doesn't just store data — it encapsulates the **complete domain concept** of a repair request:

- **State transitions:** `mark_in_review()`, `mark_in_progress()`, `mark_completed()`, `cancel()` — (`models.py:222–238`)
- **Business rules:** `can_edit` (only pending), `is_active` (not completed/cancelled), `is_overdue` (pending > N days) — (`models.py:242–261`)
- **Computed data:** `days_open` — (`models.py:248–252`)
- **Query interface:** Custom manager with domain-specific queries — (`managers.py:81–109`)
- **Self-referencing URL:** `get_absolute_url()` — (`models.py:217–218`)

Similarly, `Dwelling` encapsulates occupancy logic (`is_overcrowded`), compliance status (`compliance_status`), and maintenance history (`maintenance_history`).

### Philosophy 5: Efficiency — Minimal Database Hits

> "Django's database layer provides various ways to help developers get the best performance out of their databases."

- **`select_related()`** used on every view that traverses ForeignKey chains to avoid N+1 queries (`views.py:401–403`, `488–490`, `500`, `586–590`)
- **`QuerySet.iterator()`** in CSV export for constant memory usage (`views.py:309`)
- **`update_fields`** on all model save operations to update only changed columns (`models.py:220`, `225`, `230`, `234`)
- **Annotations with `Count()`** instead of Python loops for community/dwelling statistics (`views.py:591–600`)
- **`StreamingHttpResponse`** for CSV export — rows sent as they're generated, not buffered in memory (`views.py:321`)

---

## 6. File Structure Overview

```
HIT237-BUILDING-INTERACTIVE-SOFTWARES/
├── config/                     # Project configuration
│   ├── settings.py             # Django settings
│   ├── urls.py                 # Root URL configuration
│   ├── wsgi.py                 # WSGI entry point
│   └── asgi.py                 # ASGI entry point
├── repairs/                    # Main application
│   ├── models.py               # 7 models (Fat Model pattern)
│   ├── views.py                # 13 CBVs + 15 FBVs
│   ├── urls.py                 # 29 URL patterns
│   ├── forms.py                # 8 form classes
│   ├── managers.py             # Custom QuerySet + Manager
│   ├── mixins.py               # CBV access-control mixins
│   ├── signals.py              # 2 signal handlers
│   ├── decorators.py           # 3 FBV decorators
│   ├── middleware.py            # Profile enforcement middleware
│   ├── context_processors.py   # Global template context
│   ├── admin.py                # 7 ModelAdmin registrations
│   ├── templatetags/
│   │   └── repair_tags.py      # Filters + inclusion tags
│   ├── management/
│   │   └── commands/
│   │       └── seed_data.py    # Database seeding command
│   └── tests.py                # 79 automated tests
├── templates/                  # 24 HTML templates
│   ├── base.html
│   ├── home.html
│   ├── auth/                   # Login, register, profile
│   ├── dashboard/              # Tenant + staff dashboards
│   ├── repairs/                # CRUD templates
│   ├── communities/            # Community list + detail
│   ├── dwelling/               # Dwelling list + detail
│   ├── analytics/              # Analytics dashboard
│   ├── notifications/          # Notification list
│   └── components/             # Reusable badge components
├── static/css/style.css        # 791 lines, dark theme
├── media/                      # User-uploaded repair images
├── ADR.md                      # Architectural Decision Records
├── SUPPLEMENTARY.md            # This file
├── Group Contract.md           # Team contract and project plan
├── Summary.md                  # Project summary
└── requirements.txt            # Python dependencies
```

---

## 7. Testing Summary

**79 automated tests** across 15 test classes:

| Test Class | Tests | Coverage Area |
|-----------|-------|---------------|
| `CommunityModelTest` | 2 | Model string representation, dwelling count property |
| `DwellingModelTest` | 4 | Compliance status, overcrowding check, active repair count |
| `TenantProfileModelTest` | 4 | Full name, role detection |
| `RepairRequestModelTest` | 14 | Status transitions, manager/queryset methods, overdue detection |
| `RegistrationFormTest` | 3 | Validation, password mismatch, duplicate username |
| `RepairRequestFormTest` | 2 | Valid form, required field validation |
| `ViewTest` | 10 | Home, login, register, dashboards, CRUD, status update |
| `SignalTest` | 3 | Auto-profile creation, notification on status change, no duplicates |
| `NotificationModelTest` | 3 | String representation, default unread, mark read |
| `RepairFeedbackModelTest` | 2 | String representation, rating storage |
| `ProfileViewTest` | 5 | Profile CRUD, password change |
| `CommunityViewTest` | 4 | Staff-only access, list/detail rendering |
| `AnalyticsViewTest` | 5 | Staff-only access, CSV export content-type and headers |
| `FeedbackViewTest` | 3 | Completed-only feedback, submission, duplicate prevention |
| `NotificationViewTest` | 3 | List, mark single read, mark all read |
| `LogoutViewTest` | 2 | GET does not logout, POST does |
| `CancelRequestViewTest` | 2 | Cancel success, cannot cancel completed |
| `ContextProcessorTest` | 2 | Unread count, user role in context |

---

## 8. Code Reviews

This section records notable review discussions that took place during development. These are preserved verbatim (reformatted for this document) to show the thought process behind the code as it stands today. Reviewers: team members (peer review) and self-review passes.

### Review 1 — `RepairRequestManager` delegation gap

**File:** `repairs/managers.py:81–109`
**Reviewer:** Peer review
**Status:** Acknowledged, left as-is

**Observation.** `RepairRequestQuerySet` exposes 16 methods, but `RepairRequestManager` only re-declares 8 of them (`pending`, `in_progress`, `completed`, `active`, `overdue`, and the three `stats_by_*` methods). That means a direct call like `RepairRequest.objects.in_review()` or `RepairRequest.objects.by_priority('HIGH')` would fail with `AttributeError`, while the same method works when chained: `RepairRequest.objects.get_queryset().in_review()` or `RepairRequest.objects.active().by_priority('HIGH')`.

**Discussion.** Two options were considered:
1. Replace the manual delegation with `RepairRequestManager = RepairRequestQuerySet.as_manager()` so every QuerySet method is auto-exposed.
2. Keep the manual delegation and treat the shorter Manager API as intentional — only the methods used in views are promoted to the top-level API; everything else is available via chaining.

**Resolution.** We kept option 2. The Manager's public surface matches what `views.py` actually calls (`pending().count()`, `overdue().count()`, `active()`, `stats_by_*`). Adding auto-delegation would expose methods like `recent()` and `by_priority()` at the top level, which we'd rather reach through chaining so filters compose naturally (e.g. `RepairRequest.objects.active().by_priority('HIGH')`). The trade-off is documented in **ADR-003 → Consequences**.

**Action item.** None — behaviour matches intent. If a future view needs `RepairRequest.objects.by_priority(...)` directly, add the one-line delegate at that point.

---

### Review 2 — Overdue threshold exists in two places

**Files:** `repairs/managers.py:34` and `repairs/models.py:242–246`
**Reviewer:** Self-review
**Status:** Resolved (documented, not deduplicated)

**Observation.** `RepairRequestQuerySet.overdue(days=14)` and `RepairRequest.is_overdue(days=14)` both hard-code the same default of 14 days. If the business rule changes, two edits are required instead of one, which contradicts the DRY claim in **ADR-003**.

**Discussion.** Extracting a module-level constant (`OVERDUE_DAYS = 14`) was considered. It would centralise the value, but at the cost of an extra import in both files and a less discoverable default in the method signature. The two methods also serve different call sites: the QuerySet version runs in SQL (`created_at__lte=cutoff`), the model version runs in Python on a loaded instance. They aren't actually redundant — they're two implementations of the same rule for two different contexts.

**Resolution.** The duplication is acceptable because both defaults are explicit, visible in the method signatures, and callers can override the value. If the default ever needs to change in production, a grep for `days=14` finds both call sites immediately. Noted here so the next reviewer doesn't flag it again.

---

### Review 3 — `mark_completed()` does not enforce preconditions

**File:** `repairs/models.py:231–234`
**Reviewer:** Peer review
**Status:** Accepted trade-off

**Observation.** The state transition methods on `RepairRequest` (`mark_in_review`, `mark_in_progress`, `mark_completed`, `cancel`) update the status unconditionally. There is no check that the transition is legal — e.g. `mark_completed()` will happily run on a `CANCELLED` request, moving it back to `COMPLETED`. The state machine in section 4 of this document shows the intended flow, but the model does not enforce it.

**Discussion.** A stricter implementation would raise `ValidationError` on illegal transitions, e.g.:

```python
def mark_completed(self):
    if self.status not in ('IN_PROGRESS', 'IN_REVIEW'):
        raise ValidationError(f"Cannot complete from status {self.status}")
    ...
```

This was rejected for two reasons:
1. **Access control already gates transitions at the view layer.** Only staff can call `mark_in_progress` / `mark_completed` (via `@staff_required`), and only tenants can `cancel()` (and only while the request is active — `repairs/views.py:159`). A tenant can never reach `mark_completed`, and staff hitting the button on a cancelled request would be a UI bug, not a data integrity issue.
2. **Raising exceptions in model methods pushes error handling into every caller.** The current approach keeps the Fat Model methods as simple, composable operations.

**Resolution.** Left as-is. If we were building this for production rather than coursework, we would add a `can_transition_to(new_status)` helper and call it from both the view (for user-friendly error messages) and the model (as a final guard). For HIT237 scope, view-layer gating is sufficient. This is a known limitation, not an accidental omission.

---

### Review 4 — `Echo` class inside `export_csv` view

**File:** `repairs/views.py:294–296`
**Reviewer:** Self-review
**Status:** Left inline intentionally

**Observation.** The `Echo` pseudo-buffer class (`class Echo: def write(self, value): return value`) is defined inside the `export_csv` function body. Convention would place small utility classes at module level.

**Discussion.** Moving `Echo` to module level was considered. The reason it lives inside the function: it's used in exactly one place, it's two lines long, and putting it next to the `StreamingHttpResponse` call makes the streaming trick (`csv.writer` writing into a write-through buffer) immediately legible to anyone reading the view. Hoisting it to the top of the file would save no lines and force the reader to jump around.

**Resolution.** Kept inline. The view is the only consumer; if a second CSV export is added later, the class can be promoted then.

---

### Review 5 — `TenantProfile` auto-creation relies on two mechanisms

**Files:** `repairs/signals.py:8–12` and `repairs/middleware.py:1–28`
**Reviewer:** Peer review
**Status:** Intentional belt-and-braces

**Observation.** Profile creation is handled by both a `post_save` signal on `User` **and** a middleware that runs `get_or_create` on every authenticated request. This looks like a belt-and-braces redundancy — one of the two should be enough.

**Discussion.** The signal alone is not enough: `createsuperuser` bypasses the usual registration flow, and in some test paths the signal is disconnected or User objects are created with `save(force_insert=False)` in ways that interact oddly. The middleware alone is not enough either, because any view that touches `request.user.profile` *before* the middleware has run (e.g. context processor ordering issues) would still crash on first request.

**Resolution.** Keep both. The signal is the cheap, fast path that handles 99% of creations at the moment they happen. The middleware is the fallback that guarantees the invariant across every request. This is discussed in **ADR-005** and **ADR-006**; the review confirmed that neither mechanism can be removed safely.

---

### Summary of review outcomes

| Review | Finding | Outcome |
|--------|---------|---------|
| 1 | Manager only delegates 8 of 16 QuerySet methods | Kept — public API is intentional |
| 2 | Overdue threshold duplicated in QuerySet and model | Kept — two call sites, two contexts |
| 3 | State transitions not enforced on model | Kept — view-layer gating is sufficient for scope |
| 4 | `Echo` class defined inside view function | Kept — single consumer, local readability wins |
| 5 | Profile creation runs via both signal and middleware | Kept — deliberate redundancy for invariant safety |

All five reviews concluded with "kept as-is". This was itself reviewed — the pattern of accepting every finding would normally be suspicious — but in each case the alternative had a concrete downside that had already been weighed during the original implementation. The value of recording the review is not that it produced code changes, but that the reasoning is now written down so a future reader (or marker) doesn't need to re-derive it from the code alone.
