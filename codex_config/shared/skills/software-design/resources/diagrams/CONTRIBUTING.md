# Contributing

Thanks for helping improve the software diagrams skill.

## Development setup

1. Install Node.js 20+, Java 17+, and PowerShell 7 or Bash.
2. Run `npm ci`.
3. Run the platform bootstrap script to download the pinned Java tools.
4. Run the complete gallery render before editing examples.

## Making changes

- Keep `GUIDE.md` focused on decisions and workflow. Put lengthy tool-specific details in `references/`.
- Add or update an editable source file before changing a generated image.
- Use stable ASCII IDs in diagram sources and keep relationship labels short.
- Do not commit `node_modules/`, downloaded Java tools, temporary logs, or local caches.
- If a tool requires a network download, pin the version and record the official source URL.
- Preserve third-party license notices when adding templates, fonts, icons, or examples.

## Validation

Run:

```bash
npm ci
```

Then run the platform render script. Review the generated SVG/PNG files for clipping, overlap, unreadable text, incorrect arrows, and missing nodes. Structurizr must validate successfully before its views are exported.

## Pull requests

Describe:

- what diagram or workflow changed;
- which source and generated files changed;
- the exact render command used;
- any new dependency, version, or license consideration.

Keep pull requests focused. Do not include generated dependency directories or unrelated project files.
