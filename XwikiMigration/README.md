# XWiki CIL Migration Toolkit

This toolkit exports the Client Information Library from XWiki, inventories
and downloads attachments, produces reports, and provides starter importers
for Confluence and Jira Assets.

## Important security note

Do not store passwords or API tokens in the Python files.

Copy `.env.example` to `.env` and fill in your own values:

```powershell
Copy-Item .env.example .env
```

The previously exposed XWiki password should be changed.

## Installation

```powershell
cd XwikiMigration
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 1. Export client records

Export 50 successful CIL records:

```powershell
python export_clients.py --limit 50
```

Export 500:

```powershell
python export_clients.py --limit 500
```

## 2. Inventory attachments

Scan 500 successful CIL records without downloading:

```powershell
python inventory.py --limit 500
```

Generated files:

- `output/inventory/cil_attachment_inventory.csv`
- `output/inventory/cil_client_attachment_summary.csv`
- `output/logs/inventory_skipped_pages.csv`
- `output/logs/inventory_errors.csv`

## 3. Produce an inventory report

```powershell
python reports.py
```

The report is written to:

```text
output/logs/inventory_report.txt
```

## 4. Download attachments

Download every attachment listed in the inventory:

```powershell
python download_attachments.py
```

Download only the first 20 as a pilot:

```powershell
python download_attachments.py --limit 20
```

Downloaded files are stored under:

```text
output/attachments/<client>/
```

The result log is written to:

```text
output/inventory/cil_attachment_download_results.csv
```

## 5. Confluence pilot import

The Confluence importer defaults to dry-run mode.

Configure these values in `.env`:

```text
ATLASSIAN_BASE_URL
ATLASSIAN_EMAIL
ATLASSIAN_API_TOKEN
CONFLUENCE_SPACE_KEY
CONFLUENCE_PARENT_PAGE_ID
CONFLUENCE_DRY_RUN=true
```

Then:

```powershell
python import_confluence.py `
  --clients output\clients\cil_clients_50.csv `
  --limit 5
```

Review the generated payloads before setting:

```text
CONFLUENCE_DRY_RUN=false
```

Attachment upload to Confluence should be added after the target page model and
permissions are approved.

## 6. Jira Assets pilot import

Create the target Assets schema and object type first. Then replace the
placeholder values in `ATTRIBUTE_MAP` inside `import_jira_assets.py` with the
actual Assets attribute IDs.

Configure:

```text
JIRA_ASSETS_WORKSPACE_ID
JIRA_ASSETS_SCHEMA_ID
JIRA_ASSETS_OBJECT_TYPE_ID
JIRA_ASSETS_DRY_RUN=true
```

Run:

```powershell
python import_jira_assets.py `
  --clients output\clients\cil_clients_50.csv `
  --limit 5
```

Keep dry-run enabled until the payload and field mapping are validated.

## Recommended order

1. Export 50 records.
2. Inventory 500 records.
3. Select a representative attachment pilot.
4. Download pilot attachments.
5. Create the Confluence page template.
6. Create the Jira Assets schema.
7. Test five records in dry-run.
8. Test five real records.
9. Scale to 250, 1,000, then the full library.
