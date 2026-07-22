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

External Public Requests
========================

Purpose
-------

The module includes a public intake form for people who do not have an Odoo account. External submissions are stored separately from the internal employee workflow in model ``ab_request_website`` and are shown in the backend menu:

``Requests and Complaints → External Requests``

This keeps external submissions isolated from the employee-based ``ab_request`` workflow and avoids invoking required internal user and employee fields. Public visitors have no model ACL; the CSRF-protected controller validates and creates only the submitted external record through a narrow elevated operation.

Public Configuration
--------------------

Request administrators or HR Request Visibility Users must explicitly enable ``Available on Public Form`` on both a category and each request type that should be exposed. Existing categories and types remain private by default. The form lists only enabled options, filters types by category, and verifies the relationship again on the server.

Backend Access
--------------

- Department managers see external requests routed to request types they manage.
- HR Request Visibility Users see external complaints only.
- Request administrators see all external requests.
- Ordinary request users have no access to external submissions or outsider contact details.

External records use the controlled workflow ``New → Under Review → Closed`` and an ``EXT/<year>/`` reference. They remain separate from internal requests.

Public Routes
-------------

- ``/requests/external-form``: Arabic RTL embeddable external-customer form
- ``/requests/customer-submit``: form submit route

Embed Code
----------

Use this code inside the website custom embed/code field when the form is embedded on the same Odoo website:

.. code-block:: html

   <iframe src="/requests/external-form" style="width:100%; min-height:780px; border:0;"></iframe>

If the form is embedded from an external website, use the full production domain:

.. code-block:: html

   <iframe src="https://your-production-domain.com/requests/external-form" style="width:100%; min-height:780px; border:0;"></iframe>

Production Deployment
---------------------

1. Commit and push all ``ab_request_management`` source changes.
2. Pull the code on production into the custom addons path, for example:

   ``/opt/odoo19/custom-addons/ab_request_management``

3. Confirm the production Odoo config includes the custom addons directory in ``addons_path``:

   ``/opt/odoo19/custom-addons``

4. Upgrade the module on the production database:

.. code-block:: bash

   /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
     -c /opt/odoo19/odoo19.conf \
     -d YOUR_PROD_DB \
     -u ab_request_management \
     --stop-after-init

5. Restart the actual Odoo process serving the website so the public controller routes are loaded.
6. Hard refresh the browser after restart so the dashboard JS asset shows the new ``Website Requests`` counter.

Expected Result
---------------

- The external form loads without the website header/footer inside the iframe.
- Public submissions create records only in ``ab_request_website``.
- Authorized backend users review submissions from ``External Requests``.
- The dashboard shows an ``External Requests`` counter for new submissions.

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
