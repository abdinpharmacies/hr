# ab_payroll Payroll Sheet Telegram Distribution

This document describes the payroll sheet distribution process implemented in
`ab_payroll`.

## Purpose

The payroll sheet feature lets Payroll Administrators upload employee payroll
files and distribute them through the configured Telegram bot.

Each payroll file is matched to an employee, validated, queued, and sent to the
resolved recipient through Telegram.

## Module Dependencies

Installing `ab_payroll` installs these direct dependencies:

- `ab_hr`
- `abdin_telegram`

These optional integration modules provide automatic employee Telegram linking:

- `ab_request_telegram`
- `ab_hr_telegram_employee_link`

Install `ab_hr_telegram_employee_link` when employees should link their Telegram
chat information to their HR employee record through the bot. Payroll sheets
can still use Telegram identifiers entered directly on the employee record.

## Required Telegram Setup

1. Configure the Telegram bot token in Odoo system parameters:

   ```text
   telegram.bot.token
   ```

2. Install `ab_hr_telegram_employee_link`.

3. Ask every employee who should receive payroll files to send their HR code to
   the Telegram bot one time.

   Example:

   ```text
   6565
   ```

4. The linking module stores the employee Telegram data on the HR employee
   record, including:

   - Telegram Chat ID
   - Telegram User ID
   - Telegram Username
   - Telegram Linked At

Payroll distribution should not be used until the required employee or manager
Telegram chat IDs are saved.

## File Naming Format

Payroll files must include the employee name, HR code, and department/workplace
in the filename.

Recommended format:

```text
Employee_Full_Name_1234_Department.pdf
```

Supported file extensions:

- PDF
- XLSX

ZIP upload is supported from the payroll upload wizard for bulk uploads. ZIP
files should contain PDF/XLSX files that follow the same naming format.

## Employee Matching

The system matches the uploaded file to the employee using deterministic rules:

1. Employee cost center code
2. Badge/barcode
3. Identification ID
4. Normalized employee code
5. Exact employee name fallback

No fuzzy matching is used.

## Department and Role Matching

If an employee has one active role, that role is used for payroll routing.

If an employee has multiple active roles, the department/workplace in the file
name must match exactly one active role. This prevents sending the wrong payroll
sheet to the wrong department manager.

If the department cannot be resolved for a multi-role employee, the payroll
sheet is marked as failed and is not sent.

## Manager Resolution

The recipient manager is resolved in this order:

1. Department manager for the resolved department
2. Job manager for the resolved employee role
3. Employee direct manager
4. The employee themself, only when they are a self-managed payroll recipient

Managers can receive their own payroll file when they are the department
manager and do not have a direct manager.

## Distribution Scope

Payroll files can be distributed using one of these scopes:

- Managers Only
- Managers and Employees

When the employee and manager are the same person, only one Telegram message is
sent to avoid duplicate delivery.

## Payroll Types

Payroll type affects duplicate protection:

- Preliminary payroll sheets can be uploaded more than once.
- Final payroll sheets are protected against duplicate upload for the same
  employee, department, payroll period, payroll type, and file checksum.

## Workflow

Payroll sheet states:

```text
draft -> validated -> queued -> sent -> delivered
```

Failure and archive states:

```text
failed
archived
```

Typical process:

1. Payroll Administrator uploads payroll files.
2. The system validates file type and filename format.
3. The system matches the employee.
4. The system resolves the department and manager.
5. The system verifies required Telegram chat IDs.
6. Payroll Administrator queues distribution.
7. Queue processing sends the payroll file through Telegram.
8. The record stores Telegram status and audit history.

## Queue Distribution

Payroll files are not sent directly from the upload action.

Use one of these methods:

- Select one or more Payroll Sheets from the list view and run
  `Queue Distribution`.
- Open a Payroll Sheet and click `Queue Distribution`.
- Enable `Queue Distribution After Upload` in the upload wizard.

Queued records are processed by the payroll sheet distribution cron/job flow.

## Error Handling

The payroll sheet is marked as failed when required information is missing or
invalid.

Common failure reasons:

- Invalid filename format
- Unsupported file type
- Employee not found
- Employee has multiple active roles and the filename department does not match
  one active role
- Manager cannot be resolved
- Manager Telegram chat ID is missing
- Employee Telegram chat ID is missing when sending to employees is enabled
- Telegram sender failure

Failure details are stored in `Last Error` and the audit history.

## Security

Only Payroll Administrators and System Administrators should manage payroll
sheets.

Managers do not access the payroll sheet repository. They only receive assigned
files through Telegram.

Regular HR users should not be granted payroll sheet access.

## Separation and Upgrade Safety

The payroll sheet model keeps its existing technical name,
`ab.hr.payroll.sheet`, so existing PostgreSQL rows and attachment links remain
valid after the module split. During the first installation, `ab_payroll`
transfers the known payroll and employee Telegram XML IDs from `ab_hr` before
loading its own data. Install `ab_payroll` before performing any later
standalone upgrade of `ab_hr` in an existing database.

## Important Operational Notes

- Link employee Telegram data before payroll distribution.
- Use final payroll type only for confirmed final salary sheets.
- Use preliminary payroll type for review iterations.
- Verify failed records before retrying queue distribution.
- Do not delete payroll sheet records for audit purposes; archive instead.
