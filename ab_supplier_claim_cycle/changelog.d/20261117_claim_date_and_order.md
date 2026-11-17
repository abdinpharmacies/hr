# Claim date and entry order

- Reuse the standard Odoo date field/calendar for Claim Month with field-local ISO entry/display.
- Accept any valid calendar date, including non-first days and leap days; preserve existing dates.
- Use Name and Phone labels and place Name before Phone.
- Move Type Of Invoice after Claim Month and align submission validation order.
- Remove the obsolete month-input template. No database value conversion is required.
- Remote deployment/upgrade is manual at the user's request.
