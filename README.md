# Claude Skills

Custom Claude Code skills.

## Skills

### ones-wiki

Upload and update ONES wiki pages from local markdown files.

**Install:**
```bash
npx skills add dsy3502/claude-skills@ones-wiki
```

**Commands:**
```bash
# Login (first time only)
python ~/.claude/skills/ones-wiki/ones_client.py login --email your@email.com --password yourpassword

# List spaces
python ~/.claude/skills/ones-wiki/ones_client.py list-spaces

# Upload markdown as new page
python ~/.claude/skills/ones-wiki/ones_client.py upload <file.md> --space <space_uuid>

# Update existing page
python ~/.claude/skills/ones-wiki/ones_client.py update <file.md> --page <page_uuid>
```
