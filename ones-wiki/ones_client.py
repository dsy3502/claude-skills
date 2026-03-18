#!/usr/bin/env python3
"""
ONES Wiki Client — upload and update wiki pages from markdown files.

Two authentication modes:

  1. Classic API (full features — create + update + list)
     Login with email/password → stores Ones-Auth-Token session token.
     python ones_client.py login --email YOUR@EMAIL --password YOUR_PASSWORD

  2. Open API v2 (Bearer PAT — create + list only, no update)
     Set a Personal Access Token from ONES Profile → Developer Settings.
     python ones_client.py set-token YOUR_PAT_TOKEN

Usage:
  python ones_client.py login --email <email> --password <password>
  python ones_client.py set-token <token>
  python ones_client.py list-spaces
  python ones_client.py list-pages --space <space_uuid>
  python ones_client.py upload <markdown_file> --space <space_uuid> [--parent <page_uuid>] [--title <title>]
  python ones_client.py update <markdown_file> --page <page_uuid>  (classic API only)
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

ONES_HOST = os.environ.get("ONES_HOST", "https://ones.datacanvas.com")
CONFIG_FILE = Path.home() / ".claude" / "skills" / "ones-wiki" / ".ones_config.json"


# ── Config helpers ────────────────────────────────────────────────────────────

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass


def get_credentials():
    cfg = load_config()
    host = os.environ.get("ONES_HOST") or cfg.get("host", ONES_HOST)
    # Classic API (email/password login)
    ones_token = os.environ.get("ONES_TOKEN") or cfg.get("ones_token", "")
    user_uuid = os.environ.get("ONES_USER_UUID") or cfg.get("user_uuid", "")
    org_uuid = os.environ.get("ONES_ORG_UUID") or cfg.get("org_uuid", "")
    # team_uuid is used in wiki API paths (may differ from org_uuid)
    team_uuid = os.environ.get("ONES_TEAM_UUID") or cfg.get("team_uuid", "") or org_uuid
    # Open API v2 (PAT)
    bearer_pat = os.environ.get("ONES_PAT") or cfg.get("bearer_pat", "")
    return host, ones_token, user_uuid, org_uuid, team_uuid, bearer_pat


def has_classic_auth():
    _, ones_token, user_uuid, _, team_uuid, _ = get_credentials()
    return bool(ones_token and user_uuid and team_uuid)


def has_pat_auth():
    _, _, _, org_uuid, _, bearer_pat = get_credentials()
    return bool(bearer_pat and org_uuid)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def api_request_classic(method, path, body=None):
    """Classic ONES REST API using Ones-Auth-Token + Ones-User-Id."""
    host, ones_token, user_uuid, _, _, _ = get_credentials()
    url = f"{host}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Content-Type": "application/json",
        "Referer": host,
        "Origin": host,
        "Ones-Auth-Token": ones_token,
        "Ones-User-Id": user_uuid,
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body_bytes = e.read().decode("utf-8")
        print(f"HTTP {e.code} {e.reason}: {body_bytes}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def api_request_openapi(method, path, body=None, params=None):
    """ONES Open API v2 using Bearer PAT token."""
    host, _, _, org_uuid, _, bearer_pat = get_credentials()
    qs = f"?teamID={org_uuid}"
    if params:
        for k, v in params.items():
            qs += f"&{k}={v}"
    url = f"{host}{path}{qs}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_pat}",
        "Referer": host,
        "Origin": host,
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body_bytes = e.read().decode("utf-8")
        print(f"HTTP {e.code} {e.reason}: {body_bytes}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def api_request_openapi_multipart(path, fields):
    """POST multipart/form-data to ONES Open API v2."""
    host, _, _, org_uuid, _, bearer_pat = get_credentials()
    url = f"{host}{path}?teamID={org_uuid}"

    boundary = "----ONESBoundary" + os.urandom(8).hex()
    body_parts = []
    for key, value in fields.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{value}\r\n"
        )
    body_parts.append(f"--{boundary}--\r\n")
    body = "".join(body_parts).encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {bearer_pat}",
        "Referer": host,
        "Origin": host,
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body_bytes = e.read().decode("utf-8")
        print(f"HTTP {e.code} {e.reason}: {body_bytes}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_login(email, password):
    """Login with email/password → saves Ones-Auth-Token for classic API."""
    host, _, _, _, _, _ = get_credentials()
    # Temporarily clear token so request goes unauthenticated
    cfg_temp = load_config()
    cfg_temp_token = cfg_temp.get("ones_token", "")
    cfg_temp["ones_token"] = ""
    cfg_temp["user_uuid"] = ""
    save_config(cfg_temp)

    result = api_request_classic("POST", "/project/api/project/auth/login", {
        "email": email,
        "password": password,
    })

    # Response shape: {"user": {"uuid": ..., "token": ..., ...}, "teams": [...], "org": {...}}
    user = result.get("user", {})
    token = user.get("token", "") or result.get("token", "")
    user_uuid = user.get("uuid", "") or result.get("user_uuid", "")

    if not token:
        print("Login failed: no token in response.", file=sys.stderr)
        print(f"Response: {json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)

    # Extract team UUID (used in wiki API path) from teams list
    teams = result.get("teams", [])
    team_uuid = ""
    if teams and isinstance(teams[0], dict):
        team_uuid = teams[0].get("uuid", "")
    elif teams and isinstance(teams[0], str):
        team_uuid = teams[0]

    # Also keep org_uuid for Open API v2
    org_uuid = result.get("org", {}).get("uuid", "") or team_uuid

    if not team_uuid:
        team_uuid = input("Enter your team UUID (from browser URL): ").strip()

    cfg = load_config()
    cfg.update({
        "host": host,
        "ones_token": token,
        "user_uuid": user_uuid,
        "org_uuid": org_uuid,   # org-level UUID (QnDrfu1P)
        "team_uuid": team_uuid, # team-level UUID (Aozd1Seg) used in wiki API
    })
    save_config(cfg)
    print(f"Login successful.")
    print(f"  user_uuid : {user_uuid}")
    print(f"  team_uuid : {team_uuid}")
    print(f"  org_uuid  : {org_uuid}")
    print(f"  host      : {host}")


def cmd_set_token(pat_token, org_uuid=None):
    """Save ONES Personal Access Token (PAT) for Open API v2."""
    cfg = load_config()

    if not org_uuid:
        org_uuid = cfg.get("org_uuid", "") or cfg.get("team_uuid", "")
    if not org_uuid:
        print("Enter your ONES team/org UUID (visible in browser URL: /wiki/#/space/XXXXX)")
        org_uuid = input("org_uuid: ").strip()

    cfg.update({
        "host": ONES_HOST,
        "bearer_pat": pat_token,
        "org_uuid": org_uuid,
    })
    save_config(cfg)
    print("PAT token saved.")
    print(f"  org_uuid : {org_uuid}")
    print(f"  host     : {ONES_HOST}")
    print()
    print("Note: PAT supports list-spaces, list-pages, and upload (create).")
    print("      For update, use: login --email <email> --password <password>")


def cmd_list_spaces():
    host, _, _, org_uuid, team_uuid, _ = get_credentials()

    if has_classic_auth():
        # Use GraphQL endpoint (list-spaces REST requires AdministerWiki)
        result = api_request_classic(
            "POST",
            f"/wiki/api/wiki/team/{team_uuid}/items/graphql",
            body={"query": "{ spaces(filter: {}) { uuid name } }", "variables": {}}
        )
        spaces = result.get("data", {}).get("spaces", [])
    elif has_pat_auth():
        result = api_request_openapi("GET", "/openapi/v2/wiki/spaces")
        spaces = result.get("spaces", result if isinstance(result, list) else [])
    else:
        print("Not authenticated. Run: login --email <email> --password <password>", file=sys.stderr)
        sys.exit(1)

    if not spaces:
        print("No spaces found.")
        return []
    print(f"{'UUID':<12}  Name")
    print("-" * 60)
    for s in spaces:
        uuid = s.get("uuid", s.get("id", ""))
        title = s.get("name", s.get("title", ""))
        print(f"{uuid:<12}  {title}")
    return spaces


def cmd_list_pages(space_uuid):
    host, _, _, org_uuid, team_uuid, _ = get_credentials()

    if has_classic_auth():
        result = api_request_classic("GET",
                                     f"/wiki/api/wiki/team/{team_uuid}/space/{space_uuid}/pages?status=normal")
        pages = result.get("pages", result if isinstance(result, list) else [])
    elif has_pat_auth():
        result = api_request_openapi("GET", f"/openapi/v2/wiki/spaces/{space_uuid}/pages")
        pages = result.get("pages", result if isinstance(result, list) else [])
    else:
        print("Not authenticated.", file=sys.stderr)
        sys.exit(1)

    if not pages:
        print("No pages found.")
        return []
    print(f"{'UUID':<36}  Title")
    print("-" * 70)

    def print_pages(page_list, indent=0):
        for p in page_list:
            uuid = p.get("uuid", p.get("id", ""))
            title = p.get("title", "")
            print(f"{uuid:<36}  {'  ' * indent}{title}")
            children = p.get("children", [])
            if children:
                print_pages(children, indent + 1)

    print_pages(pages)
    return pages


def cmd_upload(md_file, space_uuid, parent_uuid=None, title=None):
    host, _, _, org_uuid, team_uuid, _ = get_credentials()
    md_path = Path(md_file)
    if not md_path.exists():
        print(f"File not found: {md_file}", file=sys.stderr)
        sys.exit(1)

    md_text = md_path.read_text(encoding="utf-8")
    page_title = title or md_path.stem.replace("-", " ").replace("_", " ").title()

    if has_classic_auth():
        content = markdown_to_html(md_text)
        body = {
            "space_uuid": space_uuid,
            "parent_uuid": parent_uuid or "",
            "title": page_title,
            "content": content,
            "status": 1,
        }
        result = api_request_classic("POST",
                                     f"/wiki/api/wiki/team/{team_uuid}/space/{space_uuid}/pages/add",
                                     body=body)
        page = result.get("page", result)
        page_uuid = page.get("uuid", "")
        print(f"Page created: {page_title}")
        print(f"  UUID : {page_uuid}")
        print(f"  URL  : {host}/wiki/#/space/{space_uuid}/page/{page_uuid}")
        return result

    elif has_pat_auth():
        content_json = markdown_to_wiz_json(md_text)
        # parentPageID: use parent_uuid if given, else use space_uuid as root
        parent_id = parent_uuid or space_uuid
        fields = {
            "parentPageID": parent_id,
            "title": page_title,
            "content": json.dumps(content_json),
        }
        result = api_request_openapi_multipart("/openapi/v2/wiki/pages", fields)
        page = result.get("page", result)
        page_uuid = page.get("uuid", page.get("id", ""))
        print(f"Page created: {page_title}")
        print(f"  UUID : {page_uuid}")
        if page_uuid:
            print(f"  URL  : {host}/wiki/#/space/{space_uuid}/page/{page_uuid}")
        return result

    else:
        print("Not authenticated.", file=sys.stderr)
        sys.exit(1)


def cmd_update(md_file, page_uuid):
    _, _, _, org_uuid, team_uuid, _ = get_credentials()
    host = load_config().get("host", ONES_HOST)

    if not has_classic_auth():
        print("Update requires classic API login (email/password).", file=sys.stderr)
        print("Run: python ones_client.py login --email <email> --password <password>",
              file=sys.stderr)
        sys.exit(1)

    md_path = Path(md_file)
    if not md_path.exists():
        print(f"File not found: {md_file}", file=sys.stderr)
        sys.exit(1)

    current = api_request_classic("GET",
                                   f"/wiki/api/wiki/team/{team_uuid}/page/{page_uuid}")
    page_info = current.get("page", current)
    space_uuid = page_info.get("space_uuid", "")

    md_text = md_path.read_text(encoding="utf-8")
    page_title = md_path.stem.replace("-", " ").replace("_", " ").title()
    content = markdown_to_html(md_text)

    body = {"title": page_title, "content": content, "status": 1}
    api_request_classic("POST",
                         f"/wiki/api/wiki/team/{team_uuid}/page/{page_uuid}/update",
                         body=body)
    print(f"Page updated: {page_title}")
    print(f"  UUID : {page_uuid}")
    if space_uuid:
        print(f"  URL  : {host}/wiki/#/space/{space_uuid}/page/{page_uuid}")


# ── Markdown → HTML (for classic API) ─────────────────────────────────────────

def markdown_to_html(md_text):
    import html as html_mod

    lines = md_text.split("\n")
    html_lines = []
    in_code = False
    in_ul = False
    in_ol = False

    def close_list():
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False

    def inline(text):
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
        return text

    for line in lines:
        if line.startswith("```"):
            if in_code:
                html_lines.append("</pre></code>")
                in_code = False
            else:
                close_list()
                lang = line[3:].strip()
                html_lines.append(f'<code><pre class="language-{lang}">')
                in_code = True
            continue
        if in_code:
            html_lines.append(html_mod.escape(line))
            continue

        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            close_list()
            level = len(m.group(1))
            html_lines.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue

        if re.match(r'^(-{3,}|_{3,}|\*{3,})$', line.strip()):
            close_list()
            html_lines.append("<hr/>")
            continue

        m = re.match(r'^[\-\*\+]\s+(.*)', line)
        if m:
            if not in_ul:
                close_list()
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue

        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            if not in_ol:
                close_list()
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue

        m = re.match(r'^>\s*(.*)', line)
        if m:
            close_list()
            html_lines.append(f"<blockquote><p>{inline(m.group(1))}</p></blockquote>")
            continue

        if not line.strip():
            close_list()
            html_lines.append("")
            continue

        close_list()
        html_lines.append(f"<p>{inline(line)}</p>")

    close_list()
    return "\n".join(html_lines)


# ── Markdown → Wiz JSON (for Open API v2) ─────────────────────────────────────

def _wiz_id():
    import random, string
    return "".join(random.choices(string.ascii_letters + string.digits, k=9))


def markdown_to_wiz_json(md_text):
    """Convert markdown to ONES Wiz editor block format."""
    lines = md_text.split("\n")
    blocks = []
    in_code = False
    code_lines = []
    code_lang = ""

    def flush_code():
        nonlocal code_lines, code_lang, in_code
        if code_lines:
            blocks.append({
                "id": _wiz_id(),
                "type": "code",
                "language": code_lang or "plain",
                "code": "\n".join(code_lines),
            })
        code_lines = []
        code_lang = ""
        in_code = False

    def inline_wiz(text):
        """Parse inline formatting into Wiz text segments."""
        segments = []
        # Simple pass: split on bold/italic/code markers
        pattern = re.compile(
            r'\*\*(.+?)\*\*|__(.+?)__|'
            r'\*(.+?)\*|_(.+?)_|'
            r'`(.+?)`|'
            r'\[(.+?)\]\((.+?)\)'
        )
        last = 0
        for m in pattern.finditer(text):
            if m.start() > last:
                segments.append({"insert": text[last:m.start()]})
            if m.group(1) or m.group(2):
                segments.append({"insert": m.group(1) or m.group(2),
                                  "attributes": {"bold": True}})
            elif m.group(3) or m.group(4):
                segments.append({"insert": m.group(3) or m.group(4),
                                  "attributes": {"italic": True}})
            elif m.group(5):
                segments.append({"insert": m.group(5),
                                  "attributes": {"code": True}})
            elif m.group(6):
                segments.append({"insert": m.group(6),
                                  "attributes": {"link": m.group(7)}})
            last = m.end()
        if last < len(text):
            segments.append({"insert": text[last:]})
        return segments if segments else [{"insert": text}]

    for line in lines:
        if line.startswith("```"):
            if in_code:
                flush_code()
            else:
                in_code = True
                code_lang = line[3:].strip()
            continue
        if in_code:
            code_lines.append(line)
            continue

        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            blocks.append({
                "id": _wiz_id(),
                "type": "text",
                "text": inline_wiz(m.group(2)),
                "heading": level,
            })
            continue

        if re.match(r'^(-{3,}|_{3,}|\*{3,})$', line.strip()):
            blocks.append({"id": _wiz_id(), "type": "divider"})
            continue

        m = re.match(r'^[\-\*\+]\s+(.*)', line)
        if m:
            blocks.append({
                "id": _wiz_id(),
                "type": "text",
                "text": inline_wiz(m.group(1)),
                "listType": "unordered",
            })
            continue

        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            blocks.append({
                "id": _wiz_id(),
                "type": "text",
                "text": inline_wiz(m.group(1)),
                "listType": "ordered",
            })
            continue

        m = re.match(r'^>\s*(.*)', line)
        if m:
            blocks.append({
                "id": _wiz_id(),
                "type": "text",
                "text": inline_wiz(m.group(1)),
                "quoted": True,
            })
            continue

        if not line.strip():
            blocks.append({"id": _wiz_id(), "type": "text", "text": []})
            continue

        blocks.append({"id": _wiz_id(), "type": "text", "text": inline_wiz(line)})

    if in_code:
        flush_code()

    return {"blocks": blocks}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ONES Wiki Client")
    sub = parser.add_subparsers(dest="cmd")

    p_login = sub.add_parser("login", help="Login with email/password (classic API)")
    p_login.add_argument("--email", required=True)
    p_login.add_argument("--password", required=True)

    p_st = sub.add_parser("set-token", help="Save PAT token for Open API v2")
    p_st.add_argument("token", help="Personal Access Token from ONES profile settings")
    p_st.add_argument("--org", default=None, help="Team/org UUID")

    sub.add_parser("list-spaces", help="List all wiki spaces")

    p_lp = sub.add_parser("list-pages", help="List pages in a space")
    p_lp.add_argument("--space", required=True, help="Space UUID")

    p_up = sub.add_parser("upload", help="Upload markdown as new page")
    p_up.add_argument("file", help="Markdown file path")
    p_up.add_argument("--space", required=True, help="Space UUID")
    p_up.add_argument("--parent", default=None, help="Parent page UUID")
    p_up.add_argument("--title", default=None, help="Page title")

    p_ud = sub.add_parser("update", help="Update existing page (classic API only)")
    p_ud.add_argument("file", help="Markdown file path")
    p_ud.add_argument("--page", required=True, help="Page UUID to update")

    args = parser.parse_args()

    if args.cmd == "login":
        cmd_login(args.email, args.password)
    elif args.cmd == "set-token":
        cmd_set_token(args.token, args.org)
    elif args.cmd == "list-spaces":
        cmd_list_spaces()
    elif args.cmd == "list-pages":
        cmd_list_pages(args.space)
    elif args.cmd == "upload":
        cmd_upload(args.file, args.space, args.parent, args.title)
    elif args.cmd == "update":
        cmd_update(args.file, args.page)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
