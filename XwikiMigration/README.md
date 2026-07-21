# XWiki CIL Migration Toolkit v1.0

A modular migration toolkit for:

- exporting CIL records from XWiki
- inventorying attachments
- downloading attachments with hashes and retry logic
- generating migration reports
- preparing Confluence and Jira Assets imports

## Setup

```powershell
cd C:\Users\chvezinet\DEV\XwikiMigration
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and enter your credentials.

## Commands

Export 50 successful client records:

```powershell
python migrate.py export-clients --limit 50
```

Inventory 500 clients:

```powershell
python migrate.py inventory --limit 500
```

Download the first 20 inventoried attachments:

```powershell
python migrate.py download --limit 20
```

Download all inventoried attachments:

```powershell
python migrate.py download
```

Generate reports:

```powershell
python migrate.py report
```

Validate configuration and connectivity:

```powershell
python migrate.py validate
```

## Output

```text
output/
  clients/
  inventory/
  attachments/
  logs/
```

## Safety

- Atlassian import commands are dry-run by default.
- Credentials are read from `.env`.
- The downloader can resume by skipping files already present.
- Errors are written to CSV logs rather than stopping the full run.
