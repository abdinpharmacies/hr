# `ab_request_management`

Technical documentation for the Odoo module `ab_request_management`.

## Overview

`ab_request_management` implements an internal request workflow on top of Odoo mail/chatter. It allows employees to submit requests, routes them to the responsible department manager, supports assignment to one or more employees, tracks immutable follow-ups, and exposes list/dashboard views for daily operations.

The module depends on:

- `base`
- `mail`
- `web`
- `ab_hr`

Declared in [__manifest__.py](/opt/odoo19/custom-addons/ab_request_management/__manifest__.py).

## Main Business Objects

### Request

Model: `ab.request`  
Table: `ab_request_ticket`

Implemented in [ab_request_ticket.py](/opt/odoo19/custom-addons/ab_request_management/models/ab_request_ticket.py).

Core fields:

- `name`: generated request number from sequence `ab_request_ticket.ticket_number`
- `subject`: immutable after creation
- `description`: immutable after creation
- `request_type_id`: request category linked to a department
- `requester_id`: current employee linked to the logged-in user
- `department_id`: related from the selected request type
- `manager_id`: related department manager
- `assigned_employee_ids`: current assignees
- `assigned_employee_id`: legacy primary assignee for backward compatibility
- `deadline`: optional planned completion date
- `state`: workflow status
- `link` and `link_ids`: related URLs and extra links
- `attachment_ids`: files attached to the request
- `followup_ids`: immutable timeline entries

Computed UI/access fields include:

- `is_requester`
- `is_department_manager`
- `is_assigned_employee`
- `is_request_admin`
- `can_assign`
- `can_work_on_request`
- `can_add_followup`
- `can_edit_assignment_details`
- `is_overdue`
- `request_role_summary`
- `request_deadline_label`
- `request_ui_summary`

### Request Type

Model: `ab.request.type`  
Table: `ab_request_type`

Implemented in [ab_request_type.py](/opt/odoo19/custom-addons/ab_request_management/models/ab_request_type.py).

Purpose:

- classify requests
- bind each type to an `ab_hr_department`
- derive the responsible manager from that department

Constraint:

- request type name must be unique per department
- the selected department must have a manager

### Follow-up

Model: `ab.request.followup`

Implemented in [ab_request_followup.py](/opt/odoo19/custom-addons/ab_request_management/models/ab_request_followup.py).

Purpose:

- append an auditable timeline entry to a request
- store the author and timestamp
- mirror the note into the request chatter

Important behavior:

- follow-ups cannot be edited
- follow-ups cannot be deleted

### Follow-up Wizard

Transient model: `ab.request.followup.wizard`

Implemented in [ab_request_followup_wizard.py](/opt/odoo19/custom-addons/ab_request_management/models/ab_request_followup_wizard.py).

Purpose:

- used when the requester asks for changes during confirmation
- posts the note to chatter
- moves the request back to `in_progress`

## Workflow

Request states:

1. `under_review`
2. `scheduled`
3. `in_progress`
4. `under_requester_confirmation`
5. `satisfied`
6. `rejected`
7. `closed`

State transitions are implemented in [ab_request_ticket.py](/opt/odoo19/custom-addons/ab_request_management/models/ab_request_ticket.py) and enforced through button actions rather than direct writes.

Typical lifecycle:

1. Requester creates a request. The record is forced into `under_review`.
2. Department manager or request admin approves it, moving it to `scheduled`.
3. Manager or admin assigns one or more employees and starts work through `action_assign`, moving it to `in_progress`.
4. Assigned employee, manager, or admin sends it to requester confirmation.
5. Requester either marks it `satisfied` or requests changes.
6. If changes are requested, the wizard adds a follow-up and returns the request to `in_progress`.
7. Assigned employee, manager, or admin closes the request once it is `satisfied` or `rejected`.

Alternative path:

- a request can be rejected directly from `under_review`
- a rejected request can still be moved to `closed`

## Business Rules

Validated in [ab_request_ticket.py](/opt/odoo19/custom-addons/ab_request_management/models/ab_request_ticket.py) and [ab_request_type.py](/opt/odoo19/custom-addons/ab_request_management/models/ab_request_type.py).

Key rules:

- `subject` and `description` are mandatory and must contain alphabetic characters
- `subject` and `description` become immutable after creation
- request numbers are unique
- request types require a department manager
- assigned employees must belong to the request department
- `deadline` cannot be in the past
- `link` must start with `http://` or `https://` if provided
- state changes are blocked unless they happen through workflow actions
- assignment fields are restricted to department managers and request admins

Compatibility note:

- `assigned_employee_id` is kept as a legacy primary assignee and synchronized from `assigned_employee_ids`

## Roles and Security

Security groups are defined in [security_groups.xml](/opt/odoo19/custom-addons/ab_request_management/security/security_groups.xml).

Available groups:

- `group_ab_request_management_user`: Request User
- `group_ab_request_management_manager`: Department Manager
- `group_ab_request_management_admin`: Request Admin

Inheritance:

- manager implies user
- admin implies manager
- `base.group_system` implies request admin
- `base.group_user` implies request user

Record rules are defined in [record_rules.xml](/opt/odoo19/custom-addons/ab_request_management/security/record_rules.xml).

Access model summary:

- regular users can see requests where they are requester or assignee
- department managers can see requests where they are the responsible manager
- request admins can see all requests and follow-ups
- follow-up creation is limited by request role and current state

Functional permissions:

- requester can create requests and confirm satisfaction
- department manager or request admin can approve, reject, assign, and edit assignment details
- assigned employee, department manager, or request admin can progress work and close eligible requests

## Notifications and Chatter

The module uses `mail.thread` and `mail.activity.mixin`.

Notification behavior:

- on creation, the responsible manager and request admins are notified
- on assignment, assignees are notified
- on requester feedback, the manager is notified
- requester, manager, and assignees are automatically subscribed to chatter

Attachments added through the form are rebound to the request record so authorized users can access them consistently.

## User Interface

Views are declared mainly in:

- [ab_request_ticket_views.xml](/opt/odoo19/custom-addons/ab_request_management/views/ab_request_ticket_views.xml)
- [ab_request_type_views.xml](/opt/odoo19/custom-addons/ab_request_management/views/ab_request_type_views.xml)
- [ab_request_followup_wizard_views.xml](/opt/odoo19/custom-addons/ab_request_management/views/ab_request_followup_wizard_views.xml)
- [ab_request_dashboard_views.xml](/opt/odoo19/custom-addons/ab_request_management/views/ab_request_dashboard_views.xml)
- [menus.xml](/opt/odoo19/custom-addons/ab_request_management/views/menus.xml)

Main menus:

- Dashboard
- My Requests
- Assigned Requests
- Review Queue
- All Requests
- Settings
- Request Types

Backend assets are loaded from the module `static/` folder and include custom JavaScript widgets, XML templates, and SCSS for:

- dashboard rendering
- request state widgets
- list renderer patching
- summary widgets

## Automated Tests

The module includes transactional tests in [test_ab_request_management.py](/opt/odoo19/custom-addons/ab_request_management/tests/test_ab_request_management.py).

Covered scenarios include:

- request creation defaults
- text validation
- immutable fields
- deadline validation
- full workflow lifecycle
- multi-assignee behavior
- follow-up permissions
- admin capabilities
- record-rule isolation

## Known Integration Points

- `ab_hr_employee` is required for requester, manager, and assignee relations
- `ab_hr_department` drives department ownership and manager routing
- `mail.thread` provides chatter and notifications
- `ir.sequence` generates request numbers

## Suggested Maintenance Notes

- if department managers change in `ab_hr`, request routing changes automatically through related fields
- if legacy code still references `assigned_employee_id`, keep the synchronization logic intact during refactors
- any future workflow expansion should continue using explicit action methods instead of direct `state` writes
