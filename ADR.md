# Architectural Decision Records (ADR)

## NT Remote Housing Repair System

This living document records every significant design decision made during the development of the NT Remote Housing Repair System. Each entry traces the decision to specific locations in the codebase.

---

## ADR-001: Fat Model Pattern for Business Logic Encapsulation

**Status:** Accepted

### Context

The repair request lifecycle involves state transitions (Pending → In Review → In Progress → Completed / Cancelled), overdue detection, and access control checks. We needed to decide where this business logic should live within the Django application architecture.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Fat Views (logic in views)** | Quick to implement; all logic visible in one place | Business rules duplicated across views; hard to test in isolation; violates DRY |
| **Service Layer (separate module)** | Clean separation; framework-agnostic | Over-engineering for Django; adds indirection; not a standard Django pattern |
| **Fat Models (logic on models)** | Testable without HTTP; single source of truth; Django-idiomatic | Models can grow large; risk of circular imports |

### Decision

We adopted the **Fat Model** pattern, placing all status transition logic, computed properties, and domain checks directly on the `RepairRequest` model. This aligns with Django's design philosophy that models should be the single, definitive source of truth about data and its behaviour.

### Code Reference

- **Status transition methods:** `repairs/models.py:222–238` — `mark_in_review()`, `mark_in_progress()`, `mark_completed()`, `cancel()`
- **Domain logic properties:** `repairs/models.py:248–261` — `days_open`, `is_active`, `can_edit`
- **Overdue detection:** `repairs/models.py:242–246` — `is_overdue(days=14)`
- **Dwelling compliance/overcrowding:** `repairs/models.py:80–95` — `is_overcrowded()`, `compliance_status`
- **Community active count:** `repairs/models.py:36–41` — `active_request_count`

### Consequences

- **Positive:** Views remain thin — they handle HTTP concerns only. Business rules are testable with unit tests that never touch the HTTP layer. Any view or management command that changes request status calls the same model method, guaranteeing consistent behaviour.
- **Trade-off:** The `RepairRequest` model is the largest model (~120 lines). This is manageable for our domain complexity but would warrant splitting into mixins if the model grew further.

---

## ADR-002: Class-Based Views with Custom Access-Control Mixins

**Status:** Accepted

### Context

The application has two user roles (tenant and maintenance staff) with distinct permissions. We initially implemented all views as function-based views (FBVs) with custom decorators. As the number of CRUD views grew, we observed significant boilerplate: every list view repeated pagination logic, every detail view repeated `get_object_or_404` with `select_related`, and every create/update view repeated form handling patterns.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Function-Based Views + decorators** | Explicit control flow; easy to read linearly | Boilerplate for CRUD; pagination/form logic repeated; decorators cannot share state |
| **Class-Based Views + Django's built-in mixins** | DRY via inheritance; built-in pagination, form handling, and queryset filtering | `LoginRequiredMixin` redirects silently (no message); `PermissionRequiredMixin` uses Django's permission system which we don't use |
| **Class-Based Views + custom mixins** | All CBV benefits plus role-based access that matches our TenantProfile model | Slightly more upfront design; dispatch chain can be harder to trace |

### Decision

We use **Class-Based Views with custom access-control mixins** for all CRUD and list views (13 CBVs), while retaining **function-based views** for procedural actions like login/logout, status updates, comments, and CSV export where CBV patterns add no value.

Custom mixins (`LoginRequiredWithMessageMixin`, `StaffRequiredMixin`, `TenantRequiredMixin`) extend Django's `LoginRequiredMixin` and override `dispatch()` to enforce role checks using our `TenantProfile.is_staff_member` field, providing user-friendly flash messages on denial.

### Code Reference

- **Custom mixins:** `repairs/mixins.py:15–52` — `LoginRequiredWithMessageMixin`, `StaffRequiredMixin`, `TenantRequiredMixin`
- **CBV examples:**
  - `RepairRequestListView(LoginRequiredWithMessageMixin, ListView)` — `repairs/views.py:397–454`
  - `RepairRequestCreateView(TenantRequiredMixin, CreateView)` — `repairs/views.py:458–486`
  - `RepairRequestDetailView(LoginRequiredWithMessageMixin, DetailView)` — `repairs/views.py:488–529`
  - `RepairRequestUpdateView(TenantRequiredMixin, UpdateView)` — `repairs/views.py:531–557`
  - `RepairRequestDeleteView(TenantRequiredMixin, DeleteView)` — `repairs/views.py:559–583`
  - `StaffDashboardView(StaffRequiredMixin, TemplateView)` — `repairs/views.py:369–394`
  - `AnalyticsView(StaffRequiredMixin, TemplateView)` — `repairs/views.py:714–760`
- **FBVs retained for actions:** `repairs/views.py:99–143` (status update), `repairs/views.py:166–202` (feedback), `repairs/views.py:281–325` (CSV export)
- **URL wiring:** `repairs/urls.py:18–47` — `.as_view()` calls for CBVs

### Consequences

- **Positive:** CRUD views are concise — `RepairRequestDeleteView` is ~25 lines vs. ~16 lines as an FBV, but gains automatic form handling, CSRF, and template rendering. The mixin hierarchy means adding a new staff-only view requires only `class NewView(StaffRequiredMixin, TemplateView)`.
- **Positive:** The hybrid approach (CBV for CRUD, FBV for actions) avoids forcing procedural logic into an awkward class structure.
- **Trade-off:** Developers must understand Django's method resolution order (MRO) and the CBV dispatch chain to debug access control issues.

---

## ADR-003: Custom Manager and QuerySet for Reusable Query Logic

**Status:** Accepted

### Context

Repair request queries are used across dashboards, list views, analytics, CSV export, and model properties. Queries like "all active requests" (`status not in [COMPLETED, CANCELLED]`) and "overdue requests" (`status=PENDING` and `created_at` older than 14 days) appeared in multiple locations.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Inline QuerySet filters in views** | No abstraction needed; visible at call site | Duplicated filter logic; changes to "active" definition require editing every view |
| **Custom Manager only** | Centralised queries; clean `RepairRequest.objects.pending()` API | Manager methods return QuerySets but are not chainable with each other by default |
| **Custom QuerySet + Manager** | Chainable: `RepairRequest.objects.active().overdue()`; aggregation methods reusable; testable in isolation | Requires two classes; method delegation from Manager to QuerySet |

### Decision

We implemented a **Custom QuerySet (`RepairRequestQuerySet`)** with all filter and aggregation methods, paired with a **Custom Manager (`RepairRequestManager`)** that delegates to it. This provides a fluent, chainable query API.

### Code Reference

- **QuerySet class:** `repairs/managers.py:6–78`
  - Filters: `pending()`, `in_review()`, `in_progress()`, `completed()`, `cancelled()`, `active()`, `overdue()` — lines 9–37
  - Parameterised filters: `by_priority()`, `by_issue_type()`, `for_community()`, `for_dwelling()` — lines 28–43
  - Aggregation methods: `stats_by_issue_type()`, `stats_by_community()`, `stats_by_status()`, `stats_by_priority()` — lines 45–75
- **Manager class:** `repairs/managers.py:81–109` — delegates to QuerySet
- **Model assignment:** `repairs/models.py:209` — `objects = RepairRequestManager()`
- **Usage in views:**
  - Staff dashboard: `repairs/views.py:375–394` — `RepairRequest.objects.pending().count()`, `.overdue().count()`, `.stats_by_issue_type()`
  - Analytics: `repairs/views.py:724–746` — aggregations for statistics
  - Model properties: `repairs/models.py:126–131` — `TenantProfile.open_requests` chains `.active()`

### Consequences

- **Positive:** The definition of "active" or "overdue" lives in exactly one place. Changing the overdue threshold from 14 to 21 days requires editing one line.
- **Positive:** Aggregation methods like `stats_by_issue_type()` return structured data directly, keeping views thin.
- **Trade-off:** The Manager must manually delegate each method it wants to expose, creating some boilerplate. Django's `Manager.from_queryset()` could reduce this but loses explicit control over the public API.

---

## ADR-004: Django Signals for Cross-Cutting Concerns

**Status:** Accepted

### Context

Two behaviours need to happen automatically across the application:
1. Every new `User` must have a corresponding `TenantProfile` created.
2. Every status change on a `RepairRequest` must generate `Notification` records for the tenant and assigned staff.

These are cross-cutting concerns — they apply regardless of whether the trigger is a view, a management command, an admin action, or a test.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Explicit calls in views** | Clear, visible; easy to debug | Must remember to call in every code path; admin actions bypass it; duplicated |
| **Model `save()` override** | Centralised; always fires | Hard to distinguish create from update; mixes save logic with side-effects; complicates testing |
| **Django Signals (`post_save`, `pre_save`)** | Fires regardless of trigger point; decoupled from model and view; standard Django pattern | Implicit — harder to trace; signal ordering can surprise |

### Decision

We use **Django Signals** for both cross-cutting concerns:
- `post_save` on `User` to auto-create `TenantProfile`
- `pre_save` on `RepairRequest` to detect status changes and create notifications

### Code Reference

- **Signal handlers:** `repairs/signals.py:8–43`
  - `create_tenant_profile` (post_save): lines 8–12
  - `notify_on_status_change` (pre_save): lines 15–43
- **Signal registration:** `repairs/apps.py:9` — `import .signals` in `ready()`
- **Tests verifying signal behaviour:** `repairs/tests.py:382–408` (`SignalTest`)

### Consequences

- **Positive:** Profile creation is guaranteed for every code path — `createsuperuser`, test factories, form registration, and admin all benefit.
- **Positive:** Notifications are decoupled from views. The `mark_in_review()` model method doesn't know about notifications; the signal handles it.
- **Trade-off:** Signals are implicit. A developer reading `mark_in_review()` won't see that a notification is created. We mitigate this with clear docstrings in `signals.py`.

---

## ADR-005: Profile Extension Pattern (OneToOne) vs Custom User Model

**Status:** Accepted

### Context

Django's built-in `User` model provides authentication, but we need additional fields (phone, dwelling assignment, staff/tenant role). We needed to decide how to extend user data.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Custom User model (`AbstractUser`)** | Single table; clean API; no extra joins | Must be done before first migration; breaks third-party app compatibility; harder to add later |
| **Custom User from scratch (`AbstractBaseUser`)** | Full control over fields and authentication | Significant boilerplate; must implement permissions, admin integration manually |
| **Profile Extension (OneToOneField)** | Works with existing User model; non-invasive; can be added at any point; leverages Django's built-in auth fully | Extra join on queries; must ensure profile exists for every user |

### Decision

We use a **Profile Extension** via `TenantProfile` with a `OneToOneField` to Django's `User` model. A `post_save` signal ensures every User has a profile, and `ProfileEnforcementMiddleware` catches edge cases (e.g., superusers created via `createsuperuser`).

### Code Reference

- **TenantProfile model:** `repairs/models.py:99–136`
  - `OneToOneField(User, related_name='profile')`: line 102
  - `ForeignKey(Dwelling, null=True, blank=True)`: lines 106–108
  - `is_staff_member` boolean: line 110
- **Auto-creation signal:** `repairs/signals.py:8–12`
- **Enforcement middleware:** `repairs/middleware.py:1–28` — `get_or_create` for users without profile
- **Profile access pattern:** `request.user.profile` used throughout views (e.g., `repairs/views.py:345`)

### Consequences

- **Positive:** We get the full power of Django's auth system (password hashing, session management, admin integration) without any custom code.
- **Positive:** The profile can be added or extended without migration headaches on the User table.
- **Trade-off:** Every query involving user data requires a join or `select_related('user')`. We use `select_related` consistently (e.g., `repairs/views.py:401–403`) to mitigate N+1 queries.

---

## ADR-006: Middleware for Profile Invariant Enforcement

**Status:** Accepted

### Context

Despite the `post_save` signal that creates `TenantProfile` on User creation (ADR-004), there's an edge case: Django's `createsuperuser` management command creates a User directly, and in some test scenarios the signal may not fire or the profile may be deleted. If a logged-in user lacks a profile, every view that accesses `request.user.profile` would crash.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Trust the signal and handle errors in views** | No middleware overhead | Every view needs try/except; one missed view = 500 error |
| **Check in a context processor** | Runs on every template render | Context processors can't redirect or block access; too late |
| **Custom middleware** | Runs before every view; can create profile or redirect; catches all edge cases | Adds to request processing chain; runs on every request |

### Decision

We use `ProfileEnforcementMiddleware` that intercepts every request for authenticated users. If no profile exists, it creates one with `get_or_create`, inheriting `is_staff` from the User model. It exempts paths like `/admin/`, `/login/`, `/logout/`, and `/register/` to avoid circular redirects.

### Code Reference

- **Middleware class:** `repairs/middleware.py:1–28`
  - Exempt paths: line 7
  - Profile creation: lines 19–22
  - Cache clearing: lines 24–26
- **Registration in settings:** `config/settings.py:50`

### Consequences

- **Positive:** The application has a hard guarantee: every authenticated user hitting any non-exempt URL has a `TenantProfile`. Views can safely use `request.user.profile` without defensive checks.
- **Trade-off:** One extra `hasattr` check per request. This is negligible compared to database queries in views.

---

## ADR-007: Role-Based Access Control via Decorators and Mixins

**Status:** Accepted

### Context

The application has two distinct user roles with different permissions:
- **Tenants** can only manage their own requests, view their own dwelling, and submit feedback.
- **Maintenance Staff** can view all data, update statuses, access analytics, manage communities/dwellings, and export data.

We needed a consistent, DRY mechanism to enforce these roles.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Django's built-in `@permission_required`** | Standard; integrates with admin permissions | Requires defining permissions per model; overkill for a two-role system; ties to Django's permission framework |
| **`if` checks inside every view** | Simple; no abstraction needed | Repeated in every view; easy to forget; inconsistent error messages |
| **Custom decorators (FBVs) + custom mixins (CBVs)** | Consistent messaging; role logic in one place; works with both FBV and CBV patterns | Two parallel systems (decorators + mixins) |

### Decision

We implement **both** custom decorators and custom mixins that share the same logic:
- **Decorators** (`@tenant_required`, `@staff_required`, `@login_required_with_message`) for the remaining FBVs
- **Mixins** (`TenantRequiredMixin`, `StaffRequiredMixin`, `LoginRequiredWithMessageMixin`) for CBVs

Both check `request.user.profile.is_staff_member` and provide consistent flash messages on denial.

### Code Reference

- **Decorators:** `repairs/decorators.py:6–48`
  - `login_required_with_message`: lines 6–14
  - `tenant_required`: lines 17–31
  - `staff_required`: lines 34–48
- **Mixins:** `repairs/mixins.py:15–52`
  - `LoginRequiredWithMessageMixin`: lines 15–22
  - `StaffRequiredMixin`: lines 25–38
  - `TenantRequiredMixin`: lines 40–52
- **Usage:**
  - FBV: `repairs/views.py:99` — `@staff_required` on `update_request_status`
  - CBV: `repairs/views.py:586` — `class CommunityListView(StaffRequiredMixin, ListView)`

### Consequences

- **Positive:** Adding a new staff-only view is one line: inherit from `StaffRequiredMixin`. Adding a new tenant-only FBV is one decorator. Consistent UX (messages, redirects) across the entire application.
- **Trade-off:** Maintaining two parallel systems (decorators for FBVs, mixins for CBVs). However, this reflects a deliberate architectural decision: we use CBVs where the pattern benefits from inheritance and FBVs where procedural flow is clearer.

---

## ADR-008: Context Processor for Global Template Data

**Status:** Accepted

### Context

Every page in the application needs to display:
1. The user's role (to show/hide navigation items)
2. The unread notification count (badge in navbar)

Without a context processor, every view function would need to add these to its context dictionary — violating DRY.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Add to every view's context manually** | Explicit; no "magic" | Violates DRY; easy to forget in new views; ~30 views to maintain |
| **Template tag that queries the database** | No view changes needed | One DB query per template tag call; harder to cache; mixes data access with presentation |
| **Context processor** | Runs once per request; available in all templates; standard Django pattern | Adds DB query to every request, even those that don't render templates (redirects) |

### Decision

We use a **custom context processor** (`global_context`) registered in `TEMPLATES` settings. It provides `user_role`, `user_profile`, and `unread_notification_count` to every template.

### Code Reference

- **Context processor:** `repairs/context_processors.py:4–14`
- **Settings registration:** `config/settings.py:66`
- **Template usage:** `templates/base.html` — navigation bar uses `user_role` for conditional rendering and `unread_notification_count` for the notification badge

### Consequences

- **Positive:** Navigation and notification badge work automatically in every template with zero view-side boilerplate.
- **Trade-off:** One `COUNT` query runs on every authenticated request. For our scale this is negligible; at higher scale we would cache the count in the session.

---

## ADR-009: Custom Template Tags for Reusable UI Components

**Status:** Accepted

### Context

Status badges (Pending, In Review, In Progress, Completed, Cancelled) and priority badges (Low, Medium, High, Emergency) appear on 6+ templates. Each needs a specific CSS class mapping. Duplicating this mapping in every template is error-prone.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Inline `{% if %}` blocks in templates** | No custom code | Massive duplication; 5+ conditions per badge; changes require editing every template |
| **CSS-only approach (class = lowercase status)** | Simple | Ties CSS class naming to model constants; fragile |
| **Custom template filters + inclusion tags** | Single source of truth for mapping; inclusion tags render complete HTML components; reusable across all templates | Requires registering a template tag library |

### Decision

We implement:
- **Template filters** (`status_class`, `priority_class`) that map status/priority values to CSS class names
- **Inclusion tags** (`status_badge`, `priority_badge`, `days_label`) that render complete badge HTML components

### Code Reference

- **Template tag library:** `repairs/templatetags/repair_tags.py:1–58`
  - `status_class` filter: lines 6–16
  - `priority_class` filter: lines 19–28
  - `status_badge` inclusion tag: lines 31–38 → renders `components/status_badge.html`
  - `priority_badge` inclusion tag: lines 41–48 → renders `components/priority_badge.html`
  - `days_label` filter: lines 51–58
- **Component templates:** `templates/components/status_badge.html`, `templates/components/priority_badge.html`

### Consequences

- **Positive:** Adding a new status (e.g., "ON_HOLD") requires updating only the filter mapping and CSS — all templates automatically reflect the change.
- **Positive:** Inclusion tags enforce consistent HTML structure for badges across the entire application.

---

## ADR-010: Streaming HTTP Response for CSV Export

**Status:** Accepted

### Context

Staff can export all repair requests as CSV. For large datasets, generating the entire CSV in memory before sending the response could consume significant memory and delay the first byte.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **`HttpResponse` with full CSV in memory** | Simple implementation | Entire dataset loaded into memory; slow time-to-first-byte for large exports |
| **Celery background task + file download** | Non-blocking; handles huge datasets | Requires Celery + Redis infrastructure; complex for a course project |
| **`StreamingHttpResponse` with generator** | Rows streamed as they're produced; constant memory usage; first byte sent immediately | Cannot set `Content-Length` header; slightly more complex code |

### Decision

We use `StreamingHttpResponse` with a generator function and `QuerySet.iterator()` to stream CSV rows one at a time. An `Echo` class acts as a pseudo-buffer for Python's `csv.writer`.

### Code Reference

- **Export view:** `repairs/views.py:281–325`
  - `Echo` class (write-through buffer): lines 299–300
  - Generator function `rows()`: lines 302–319
  - `queryset.iterator()`: line 309 — bypasses QuerySet cache for memory efficiency
  - `StreamingHttpResponse`: lines 321–325

### Consequences

- **Positive:** Memory usage is O(1) regardless of dataset size — rows are streamed directly to the client.
- **Positive:** Supports query parameter filtering (`?status=PENDING&issue_type=AC`) for targeted exports.
- **Trade-off:** The streaming response cannot report its total `Content-Length`, so browsers show an indeterminate download progress bar.

---

## ADR-011: Modelling Relationships and Data Integrity

**Status:** Accepted

### Context

The domain involves multiple related entities: communities contain dwellings, dwellings house tenants, tenants submit repair requests, staff are assigned to requests, and requests accumulate logs, notifications, and feedback. We needed to model these relationships correctly to ensure referential integrity and enable efficient queries.

### Alternatives Considered

For each relationship, we considered the appropriate Django field type:

| Relationship | Choice | Rationale |
|-------------|--------|-----------|
| User → TenantProfile | `OneToOneField` | Each user has exactly one profile; enforced at DB level |
| RepairRequest → RepairFeedback | `OneToOneField` | Exactly one feedback per completed request |
| Dwelling → Community | `ForeignKey(CASCADE)` | Many dwellings per community; deleting a community removes its dwellings |
| TenantProfile → Dwelling | `ForeignKey(SET_NULL, null=True)` | Tenant may not be assigned yet; dwelling deletion shouldn't delete profiles |
| RepairRequest → assigned_to | `ForeignKey(SET_NULL, null=True)` | Staff may not be assigned yet; staff profile deletion shouldn't cascade to requests |
| MaintenanceLog → RepairRequest | `ForeignKey(CASCADE)` | Logs are owned by the request; request deletion removes its audit trail |

### Decision

We use Django's relationship fields with explicit `on_delete` behaviours and `related_name` attributes on every relationship. This enables reverse lookups (e.g., `dwelling.repair_requests.active()`) and clear, self-documenting code.

### Code Reference

- **OneToOne relationships:**
  - `TenantProfile.user`: `repairs/models.py:102–103`
  - `RepairFeedback.repair_request`: `repairs/models.py:326–327`
- **ForeignKey with CASCADE:**
  - `Dwelling.community`: `repairs/models.py:55–56`
  - `RepairRequest.tenant`: `repairs/models.py:182–183`
  - `RepairRequest.dwelling`: `repairs/models.py:185–186`
  - `MaintenanceLog.repair_request`: `repairs/models.py:267–268`
- **ForeignKey with SET_NULL:**
  - `TenantProfile.dwelling`: `repairs/models.py:106–108`
  - `RepairRequest.assigned_to`: `repairs/models.py:201–203`
  - `Notification.related_request`: `repairs/models.py:305–307`
- **Related names used in queries:**
  - `dwelling.repair_requests.active()` — `repairs/models.py:73–74`
  - `community.dwellings.count()` — `repairs/models.py:33`
  - `repair.logs.select_related()` — `repairs/views.py:517`

### Consequences

- **Positive:** Explicit `on_delete` behaviour documents the business rule (e.g., "deleting a dwelling does NOT delete its tenants, it sets their dwelling to null").
- **Positive:** `related_name` attributes enable expressive ORM queries without hard-coding reverse relation names.
- **Positive:** `OneToOneField` on `RepairFeedback` enforces the "one feedback per repair" rule at the database level — no application-level checks needed.

---

## ADR-012: Hybrid Form Pattern for Multi-Model Updates

**Status:** Accepted

### Context

The profile editing page needs to update fields across two models simultaneously: `User` (first_name, last_name) and `TenantProfile` (phone, dwelling). Django's `ModelForm` binds to a single model.

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| **Two separate ModelForms rendered together** | Each form is simple; standard Django pattern | View must handle two form instances; validation and error display become complex |
| **Single ModelForm on TenantProfile + manual User update** | One form object | Mixes model form with manual field handling; unclear responsibility |
| **Custom Form (not ModelForm) that updates both models** | Full control; single form validation; clean `save(user)` API | Must manually define all fields and wire initial values |

### Decision

We use a **custom `Form` subclass** (`ProfileEditForm`) that defines fields from both models, populates initial values from both in `__init__`, and updates both models in `save()`. The `save()` method uses `update_fields` to avoid unnecessary database writes.

### Code Reference

- **ProfileEditForm:** `repairs/forms.py:105–135`
  - Dual-model initialisation: lines 117–124
  - Dual-model save with `update_fields`: lines 126–134
- **View usage:** `repairs/views.py:252–263`

### Consequences

- **Positive:** Single form instance in the view; single validation pass; simple template rendering.
- **Positive:** `update_fields` ensures only changed columns are written, improving performance and avoiding race conditions on unchanged fields.
- **Trade-off:** The form is tightly coupled to both `User` and `TenantProfile` schemas. Adding a field to either model requires updating the form.
