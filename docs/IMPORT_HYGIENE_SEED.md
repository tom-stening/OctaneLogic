# Import Hygiene Maintenance Seed

This repository uses a recurring import/dependency hygiene routine.

## Monthly Routine

Run from repo root:

```bash
python scripts/import_hygiene_audit.py --output docs/IMPORT_OPTIMIZATION_REPORT.md --json status/import_optimization_report.json
```

Then:
- Fix unused imports (ruff F401) where safe.
- Review declared-but-not-imported dependencies for removal or optionalisation.
- Review imported-but-undeclared modules and add explicit dependency declarations if needed.
- Record accepted actions in changelog/release notes.
