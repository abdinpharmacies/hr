# ab_request_management

Technical documentation for the Odoo module ``ab_request_management``.

Overview
========

``ab_request_management`` implements an internal request workflow on top of Odoo mail/chatter. It allows employees to submit requests, routes them to the responsible department manager, supports assignment to one or more employees, tracks immutable follow-ups, and exposes list/dashboard views for daily operations.

The module depends on:

- base
- mail
- web
- ab_hr

Declared in ``__manifest__.py``.

Main Business Objects
======================

Request
-------

Model: ``ab.request``  
Table: ``ab_request_ticket``

Core fields:

- name: generated request number (sequence)
- subject: immutable after creation
- description: immutable after creation
- request_type_id: request category linked to department
- employee_id: requester employee
- department_id: derived from request type
- manager_id: responsible department manager
- assigned_employee_ids: assigned employees
- assigned_employee_id: legacy primary assignee
- deadline: optional due date
- state: workflow status
- link, link_ids: external references
- attachment_ids: files
- followup_ids: immutable timeline

Request Type
------------

Model: ``ab.request.type``

Purpose:

- classify requests
- bind request to department
- derive responsible manager

Rules:

- unique per department
- department must have a manager

Follow-up
---------

Model: ``ab.request.followup``

Purpose:

- audit timeline entries
- store author and timestamp
- sync with chatter

Rules:

- cannot be edited
- cannot be deleted

Follow-up Wizard
----------------

Model: ``ab.request.followup.wizard``

Purpose:

- used during requester feedback
- adds follow-up
- returns request to in_progress

Workflow
========

States:

under_review → scheduled → in_progress → under_requester_confirmation → satisfied → rejected → closed

Lifecycle:

1. Request created → under_review  
2. Manager/admin approves → scheduled  
3. Assignment → in_progress  
4. Sent to requester confirmation  
5. Requester:
   - satisfied → close
   - request changes → back to in_progress  
6. Closed by authorized roles  

Business Rules
==============

- subject & description required
- immutable after creation
- unique request numbers
- deadline cannot be in past
- link must be http/https
- assignments restricted to department
- state changes only via actions

Roles & Security
================

Groups:

- User
- Manager
- Admin

Hierarchy:

Admin → Manager → User

Notifications
=============

- On creation → manager + admins notified
- On assignment → assignees notified
- On feedback → manager notified

Telegram Module
===============

Purpose
-------

Integrates Odoo requests with Telegram notifications to managers using chat_id mapping.

Installation
------------

Step 1: Install module ``Request_Telegram_Notification``

Step 2: Add system parameter:

telegram.bot.token = 8751357580:AAHRiqynnOv9PBzKzQRu0UNo-jj_ijAbFWA

Step 3: Get chat IDs:

https://api.telegram.org/bot8751357580:AAHRiqynnOv9PBzKzQRu0UNo-jj_ijAbFWA/getUpdates

Step 4: Bind in Odoo (model ``ab_hr_bot``):

- Employee / Manager ID
- chat_id

Workflow
--------

1. User submits request  
2. System selects manager  
3. chat_id resolved  
4. Telegram message sent  
5. Manager processes request  

Binding Rules
-------------

Case A: Chat ID conflict → block + notify  
Case B: Employee conflict → block + notify  
Case C: Exact match → no action  
Case D: New binding → create record  

Expected Result
---------------

✔ Request created  
✔ Manager resolved  
✔ Telegram notification sent  
✔ No duplicate bindings  