# Local Print Bridge (Client Printers)

This bridge lets Bill Wizard print using printers installed on the client PC.

## Start

From `ab_sales/tools`:

```bat
run_local_print_bridge.bat
```

Or:

```bat
python local_print_bridge.py
```

Default URL:

`http://127.0.0.1:19100`

## Endpoints

- `GET /health`
- `GET /printers`
- `POST /print_html` with JSON: `{"html": "...", "printer_name": "..."}`  
  `printer_name` can be empty to use local default printer.

## Notes

- Keep the bridge running on every client machine that needs direct print.
- Bill Wizard "Client Bridge URL" should match the running bridge URL.
