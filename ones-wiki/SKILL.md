---
name: ones-wiki
description: Upload and update ONES wiki pages from local markdown files. Use when the user wants to upload markdown to ONES wiki, update an existing ONES page, list wiki spaces or pages, or import documentation into ONES at ones.datacanvas.com.
---

# ONES Wiki Skill

Upload and update ONES wiki pages from local markdown files.

**ONES instance**: https://ones.datacanvas.com/

## Trigger

Use this skill when the user wants to:
- Upload a markdown file to ONES wiki
- Update an existing ONES wiki page
- List ONES wiki spaces or pages
- Import documentation into ONES

## Authentication

There are two authentication modes. **Classic API** (email/password) is recommended
for full functionality including page updates.

### Mode 1: Classic API — Full Features (recommended)

Login with email/password. Supports: list spaces, list pages, create page, **update page**.

```bash
python ~/.claude/skills/ones-wiki/ones_client.py login \
  --email your@email.com --password yourpassword
```

This saves `Ones-Auth-Token` to config. Only needed once until token expires.

### Mode 2: Open API v2 — Bearer PAT (no update support)

Generate a Personal Access Token (PAT) from ONES profile:
1. Log into ONES → click profile avatar → Developer Settings → Personal Access Tokens
2. Generate a new token, copy it
3. Run:

```bash
python ~/.claude/skills/ones-wiki/ones_client.py set-token YOUR_PAT_TOKEN --org TEAM_UUID
```

The `TEAM_UUID` (org_uuid) appears in your browser URL: `ones.datacanvas.com/wiki/#/space/XXXXXXXX/...`
Take the 8-character ID from the URL.

**Important**: The PAT from developer settings is NOT the same as the JWT you see in browser
devtools. The ONES REST API does not accept browser session JWTs.

## Commands

### List spaces

```bash
python ~/.claude/skills/ones-wiki/ones_client.py list-spaces
```

### Upload a new page

```bash
python ~/.claude/skills/ones-wiki/ones_client.py upload <file.md> --space <space_uuid>
```

Options:
- `--title "Custom Title"` — override title (default: filename)
- `--parent <page_uuid>` — make it a sub-page

### Update an existing page (classic API only)

```bash
python ~/.claude/skills/ones-wiki/ones_client.py update <file.md> --page <page_uuid>
```

### List pages in a space

```bash
python ~/.claude/skills/ones-wiki/ones_client.py list-pages --space <space_uuid>
```

## How to Use This Skill

When the user says things like "upload README.md to ONES" or "update the ONES page for cluster API":

1. **Check credentials first**: Run `list-spaces`. If it fails, prompt the user to login.

2. **If uploading new page**:
   - Ask which space to upload to (or run `list-spaces` to show options)
   - Ask for optional parent page and title
   - Run `upload` command

3. **If updating existing page**:
   - Requires classic API (email/password login)
   - Ask for the page UUID, or run `list-pages --space <uuid>` to find it
   - Run `update` command

4. **Show result**: Display the page URL after success.

## Notes

- **Classic API**: content is converted Markdown → HTML automatically
- **Open API v2 (PAT)**: content uses ONES Wiz editor block format
- Supports: headings, bold, italic, code blocks, lists, blockquotes, links
- Page title defaults to the filename (spaces-and-underscores → Title Case)
- Config stored at `~/.claude/skills/ones-wiki/.ones_config.json` (chmod 600)
