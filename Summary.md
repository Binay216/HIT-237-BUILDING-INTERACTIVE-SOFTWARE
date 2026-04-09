# NT Remote Housing Repair System — Project Summary

## Overview

The NT Remote Housing Repair System is a Django web application designed to manage housing repair requests across remote Northern Territory communities. It connects tenants in remote communities with maintenance staff, enabling them to report, track, and resolve housing issues such as broken air conditioning, plumbing leaks, electrical faults, roof damage, and structural problems.

The NT has a public housing waitlist of almost 6,000 people and a homelessness rate 12 times the national average. This system supports the housing maintenance effort by providing a transparent, trackable repair workflow for tenants and staff alike.

---

## Technology Stack

- **Backend:** Django 6.0 (Python)
- **Database:** SQLite3
- **Frontend:** Plain HTML + CSS (no frameworks)
- **Architecture:** Fat Model pattern with custom managers, function-based views, and Django signals

---

## Core Features

### 1. User Authentication & Roles

- **Registration** — New tenants can create an account with username, name, phone, and optional dwelling assignment.
- **Login / Logout** — Secure authentication with role-based redirection (tenants go to tenant dashboard, staff go to staff dashboard). Logout is POST-only for CSRF protection.
- **Two user roles:**
  - **Tenant** — Can submit, edit, cancel, and track their own repair requests, leave feedback on completed repairs.
  - **Maintenance Staff** — Can view all requests across all communities, update statuses, add maintenance notes, browse communities/dwellings, view analytics, and export data.
- **Auto-profile creation** — A Django signal automatically creates a TenantProfile whenever a new User is created, ensuring every user has a profile.
- **Profile management** — Users can edit their name, phone number, and dwelling assignment.
- **Password change** — Users can change their password using Django's built-in password validation (minimum length, common password check, numeric-only check, similarity check).

### 2. Repair Request Management

- **Submit requests** — Tenants can create repair requests specifying:
  - Title and description
  - Issue type (Air Conditioning, Plumbing, Electrical, Door/Lock, Roof/Ceiling, Structural, Pest Control, Other)
  - Priority level (Low, Medium, High, Emergency)
  - Location within the dwelling (Kitchen, Bathroom, Bedroom, Living Room, Laundry, External/Yard, Whole House, Other)
  - Optional image attachment
- **Edit requests** — Tenants can edit their own requests while they are still in Pending status.
- **Delete requests** — Tenants can delete their own Pending requests.
- **Cancel requests** — Tenants can cancel any of their active (non-completed, non-cancelled) requests. Cancellation is logged in the maintenance log.
- **View request details** — Full detail page showing status, priority, issue type, location, dwelling info, assigned staff, submission date, completion date, attached image, maintenance log history, and feedback.

### 3. Status Workflow

Repair requests follow a defined lifecycle:

1. **Pending** — Initial status after submission.
2. **In Review** — Staff has acknowledged and is reviewing the request.
3. **In Progress** — Staff has been assigned and work is underway.
4. **Completed** — Repair work is finished (completion timestamp recorded).
5. **Cancelled** — Request was cancelled by the tenant.

Each status transition is:
- Handled by dedicated model methods (Fat Model pattern).
- Automatically logged in the maintenance log.
- Triggers in-app notifications to the tenant (and assigned staff if applicable).

### 4. Staff Dashboard & Actions

- **Dashboard overview** — Displays counts for pending, in-progress, completed, and overdue (14+ days) requests.
- **Emergency requests** — Highlights emergency-priority requests at the top.
- **Requests by issue type** — Aggregated table showing how many requests exist per issue category.
- **Requests by community** — Aggregated table showing request distribution across communities.
- **Recent active requests** — Table of the most recent active requests with tenant, priority, status, and date.
- **Status updates** — Staff can change the status of any request and optionally add a maintenance note in one action.
- **Maintenance notes** — Staff can add detailed notes to any request, creating an audit trail.
- **Quick links** — Direct access to communities, dwellings, analytics, and CSV export from the dashboard.

### 5. Tenant Dashboard

- **Personal overview** — Shows the tenant's open request count and completed request count.
- **Dwelling info** — Links to the tenant's assigned dwelling details.
- **Recent requests** — Table of the tenant's most recent repair requests with issue type, priority, status, and date.
- **Quick actions** — Submit new request, view all requests.

### 6. Community & Dwelling Management

- **Community list** (staff only) — Browse all NT remote communities with region, population, dwelling count, and active request count. Paginated.
- **Community detail** (staff only) — View a specific community's information and all its dwellings with active request counts.
- **Dwelling list** (staff only) — Browse all dwellings across all communities. Filterable by community. Paginated.
- **Dwelling detail** — View dwelling information including address, community, type, bedrooms, year built, NCC compliance status, active repair count, and total request count. Shows active repair requests and completed maintenance history.
- **NCC compliance tracking** — Each dwelling tracks whether it meets National Construction Code standards.
- **Overcrowding check** — Model method to check if a dwelling is overcrowded based on the Canadian National Occupancy Standard (more than 2 persons per bedroom).

### 7. Analytics & Reporting

- **Analytics dashboard** (staff only) — Comprehensive statistics page showing:
  - Total requests, pending, in-progress, completed, and overdue counts.
  - Average days to complete a repair.
  - Average tenant rating and total feedback count.
  - Requests by month (last 6 months).
  - Requests broken down by status, issue type, priority, and community.
- **CSV export** (staff only) — Download all repair requests as a CSV file containing ID, title, tenant, community, dwelling, issue type, priority, status, location, created date, completed date, days open, and assigned staff. Supports filtering by status and issue type via query parameters.

### 8. Tenant Feedback

- **Rate completed repairs** — After a repair is marked as completed, the tenant can submit a rating (1–5) and an optional comment.
- **One feedback per request** — Enforced at the database level (OneToOne relationship).
- **Feedback visibility** — Feedback is displayed on the request detail page for both the tenant and staff.
- **Staff notification** — When a tenant submits feedback, the assigned staff member receives an in-app notification with the rating.

### 9. In-App Notifications

- **Automatic notifications** — Generated via Django signals when:
  - A repair request's status changes (notifies the tenant and assigned staff).
  - A tenant submits feedback (notifies the assigned staff).
- **System notifications** — Welcome messages and administrative alerts.
- **Notification types:** Status Change, New Assignment, Feedback Received, System.
- **Unread count** — Displayed as a badge in the navigation bar on every page (via context processor).
- **Notification list** — Paginated list of all notifications with read/unread styling.
- **Mark as read** — Click a notification to mark it read and navigate to the related request. Bulk "Mark All as Read" button available.

### 10. Request Filtering & Search

- **Filter by status** — All Statuses, Pending, In Review, In Progress, Completed, Cancelled.
- **Filter by issue type** — All Issue Types, Air Conditioning, Plumbing, Electrical, Door/Lock, Roof/Ceiling, Structural, Pest Control, Other.
- **Filter by priority** — All Priorities, Low, Medium, High, Emergency.
- **Search** (staff only) — Full-text search across request title, description, tenant name, dwelling address, and community name.
- **Pagination** — 10 requests per page with filter parameters preserved across pages.

### 11. Maintenance Log (Audit Trail)

- Every status change, staff note, and tenant comment is recorded as a MaintenanceLog entry.
- Each log entry records the author, timestamp, note text, and status change (if applicable).
- The full log is displayed on each request's detail page in reverse chronological order.

---

## Data Models

| Model | Purpose |
|-------|---------|
| **Community** | Represents a remote NT community (name, region, population) |
| **Dwelling** | A house/unit within a community (address, type, bedrooms, NCC compliance) |
| **TenantProfile** | Extends Django User with phone, dwelling assignment, and staff/tenant role |
| **RepairRequest** | Core model for repair requests with full status lifecycle |
| **MaintenanceLog** | Audit trail for all changes and notes on repair requests |
| **Notification** | In-app notifications for status changes, feedback, and system alerts |
| **RepairFeedback** | Tenant rating (1–5) and comment for completed repairs |

---

## Django Architecture Highlights

| Component | Implementation |
|-----------|---------------|
| **Signals** | Auto-create profile on user registration; auto-create notifications on status changes |
| **Context Processor** | Global template context providing user role and unread notification count |
| **Custom Middleware** | Profile enforcement — ensures every authenticated user has a TenantProfile |
| **Custom Manager/QuerySet** | Chainable filters (pending, active, overdue, etc.) and aggregation methods (stats by issue, community, status, priority) |
| **Custom Decorators** | `@login_required_with_message`, `@tenant_required`, `@staff_required` for role-based access control |
| **Custom Template Tags** | Filters for status/priority CSS classes and human-readable day labels; inclusion tags for badge components |
| **Fat Model Pattern** | Business logic (status transitions, overdue checks, compliance) lives on the model, not in views |
| **Seed Data Command** | `python manage.py seed_data` populates 7 communities, 8 dwellings, 4 users, 6 repair requests, maintenance logs, notifications, and feedback |

---

## Security Features

- CSRF protection on all forms (including POST-only logout).
- Role-based access control — tenants cannot access staff views and vice versa.
- Tenants can only view, edit, and delete their own requests.
- Tenants can only view their own dwelling details.
- Password validation using Django's built-in validators.
- Profile enforcement middleware prevents access without a valid profile.

---

## URL Routes (29 total)

| Category | Routes |
|----------|--------|
| Home | `/` |
| Authentication | `/register/`, `/login/`, `/logout/` |
| Profile | `/profile/`, `/profile/password/` |
| Dashboards | `/dashboard/`, `/dashboard/tenant/`, `/dashboard/staff/` |
| Repair Requests | `/requests/`, `/requests/create/`, `/requests/<id>/`, `/requests/<id>/edit/`, `/requests/<id>/delete/`, `/requests/<id>/cancel/`, `/requests/<id>/update-status/`, `/requests/<id>/comment/`, `/requests/<id>/feedback/` |
| Communities | `/communities/`, `/communities/<id>/` |
| Dwellings | `/dwellings/`, `/dwelling/<id>/` |
| Analytics & Export | `/analytics/`, `/export/csv/` |
| Notifications | `/notifications/`, `/notifications/<id>/read/`, `/notifications/mark-all-read/` |

---

## Test Coverage

**79 automated tests** covering:

- Model behaviour (Community, Dwelling, TenantProfile, RepairRequest, MaintenanceLog, Notification, RepairFeedback)
- Custom manager and queryset methods
- Form validation (registration, repair request, feedback)
- Signal behaviour (auto-profile creation, status change notifications, no duplicate profiles)
- View access control and functionality (home, login, register, dashboards, CRUD operations, status updates, feedback, cancellation, notifications, profile, password change, communities, analytics, CSV export)
- Context processor (unread count, user role)
- Logout security (POST-only)

---

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Seed the database with sample data
python manage.py seed_data

# Run the development server
python manage.py runserver

# Run tests
python manage.py test repairs
```

### Demo Accounts (after seeding)

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Superuser / Staff |
| mike | pass1234 | Maintenance Staff |
| sarah | pass1234 | Tenant (12 Main Road, Wadeye) |
| david | pass1234 | Tenant (5 Creek Street, Wadeye) |
| emily | pass1234 | Tenant (8 Bush Lane, Maningrida) |
