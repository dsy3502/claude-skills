# ONES Wiki Skill

Upload and update ONES wiki pages from local markdown files.

**ONES instance**: https://ones.datacanvas.com/

## Trigger

Use this skill when the user wants to:
- Upload a markdown file to ONES wiki
- Update an existing ONES wiki page
- List ONES wiki spaces or pages
- Import documentation into ONES

## Setup (First Use)

The skill uses a Python client script located at:
```
~/.claude/skills/ones-wiki/ones_client.py
```

Credentials are stored in `~/.claude/skills/ones-wiki/.ones_config.json` (chmod 600).

### Step 1: Login

```bash
python ~/.claude/skills/ones-wiki/ones_client.py login --email YOUR_EMAIL --password YOUR_PASSWORD
```

This saves token, user_id, and team_uuid to config. **Only needed once.**

### Step 2: Get your Space UUID

```bash
python ~/.claude/skills/ones-wiki/ones_client.py list-spaces
```

Copy the UUID of the target space.

## Commands

### Upload a new page

```bash
python ~/.claude/skills/ones-wiki/ones_client.py upload <file.md> --space <space_uuid>
```

Options:
- `--title "Custom Title"` — override title (default: filename)
- `--parent <page_uuid>` — make it a sub-page

### Update an existing page

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
   - Ask for the page UUID, or run `list-pages --space <uuid>` to find it
   - Run `update` command

4. **Show result**: Display the page URL after success.

## Environment Variables (alternative to config file)

```bash
export ONES_HOST=https://ones.datacanvas.com
export ONES_EMAIL=your@email.com
export ONES_PASSWORD=yourpassword
# OR after first login:
export ONES_TOKEN=your_token
export ONES_USER_ID=your_user_id
export ONES_TEAM_UUID=your_team_uuid
```

## Notes

- Content is converted from Markdown to HTML automatically
- Supports: headings, bold, italic, code blocks, lists, blockquotes, links
- Page title defaults to the filename (spaces-and-underscores → Title Case)
- Config file is saved with 600 permissions (user-readable only)
