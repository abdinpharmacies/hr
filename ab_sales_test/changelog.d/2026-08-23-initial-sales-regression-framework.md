# Current changes before commit:

- Add `ab_sales_test` as a data-driven sales regression harness.
- Store all invoice regression examples in a single JSON dataset.
- Add a persistent case/status model, backend views, JSON sync, generic runner, and strict fake E-Plus boundary.
- Use structured JSON scenarios as the regression dataset source.
- Declare the HR dependency used by employee/operator fixtures.
- Ignore generated Python cache files inside the module.
- Add Arabic translation files for the regression UI and diagnostics.
- Keep `expected_itm_dis_per` and all asserted line/header values under JSON `expected` objects so expected outputs are never injected into production setup inputs.
- Treat the sales employee E-Plus id as an internal technical fixture instead of a required scenario input.
- Add a scoped replica fixture-create guard so isolated test master records can be prepared on replica-style test databases without changing production modules.
- Support real contract fixture inputs for product-card contract rules and product-origin contract discounts without deriving them from expected line discounts.
- Leave contract store restrictions, contract E-Plus customer overrides, and promo store/replica scopes unset unless JSON supplies them explicitly.
- Add promo fixture support for real production fields such as `apply_disc_on`, `disc_percent`, `fixed_price`, product scopes, discount scopes, UoM basis, repetition settings, and rule domains.
- Keep contract and promo scenarios blocked when the JSON lacks genuine production configuration required to reproduce the original business path.
- Disable manual case creation in the backend so cases are created only by JSON synchronization.
- Add supplied origin-based contract discount inputs and the supplied on-order promo configuration to the JSON dataset.
- Allow JSON to pass the real `ab_sales_header.total_invoice_discount` input when explicitly supplied.
- Replace the incorrect `CONTRACT_100` fixture with the corrected source invoice and expected results.
- Add JSON-backed technical POS employee session fixtures for databases that have `ab_employee_access_sales` installed.
- Declare `ab_employee_access_sales` as an explicit dependency and force a POS HR session token before `pos_submit()`.

Files changed:

- `ab_sales_test/__init__.py`
- `ab_sales_test/__manifest__.py`
- `ab_sales_test/.gitignore`
- `ab_sales_test/models/__init__.py`
- `ab_sales_test/models/test_case.py`
- `ab_sales_test/i18n/ab_sales_test.pot`
- `ab_sales_test/i18n/ar.po`
- `ab_sales_test/i18n/ar_001.po`
- `ab_sales_test/services/__init__.py`
- `ab_sales_test/services/json_loader.py`
- `ab_sales_test/services/fake_eplus.py`
- `ab_sales_test/services/test_runner.py`
- `ab_sales_test/data/test_cases.json`
- `ab_sales_test/security/ir.model.access.csv`
- `ab_sales_test/views/test_case_views.xml`
