#!/usr/bin/env python3
"""
ONES Wiki Client - Upload and update wiki pages from markdown files.
Usage:
  python ones_client.py upload <markdown_file> [--space <space_uuid>] [--parent <parent_page_uuid>] [--title <title>]
  python ones_client.py update <markdown_file> --page <page_uuid>
  python ones_client.py list-spaces
  python ones_client.py list-pages --space <space_uuid>
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
ONES_EMAIL = os.environ.get("ONES_EMAIL", "")
ONES_PASSWORD = os.environ.get("ONES_PASSWORD", "")
ONES_TOKEN = os.environ.get("ONES_TOKEN", "")
ONES_USER_ID = os.environ.get("ONES_USER_ID", "")
ONES_TEAM_UUID = os.environ.get("ONES_TEAM_UUID", "")

CONFIG_FILE = Path.home() / ".claude" / "skills" / "ones-wiki" / ".ones_config.json"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return cfg
    return {}


def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)
    print(f"Config saved to {CONFIG_FILE}")


def get_credentials():
    cfg = load_config()
    host = ONES_HOST or cfg.get("host", "https://ones.datacanvas.com")
    token = ONES_TOKEN or cfg.get("token", "")
    user_id = ONES_USER_ID or cfg.get("user_id", "")
    team_uuid = ONES_TEAM_UUID or cfg.get("team_uuid", "")
    return host, token, user_id, team_uuid


def api_request(method, path, body=None, token=None, user_id=None, host=None):
    if host is None:
        host, token, user_id, _ = get_credentials()
    url = f"{host}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    headers = {
        "Content-Type": "application/json",
        "Referer": host,
    }
    if token:
        headers["Ones-Auth-Token"] = token
    if user_id:
        headers["Ones-User-Id"] = user_id

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def login(email=None, password=None):
    host, _, _, _ = get_credentials()
    email = email or ONES_EMAIL
    password = password or ONES_PASSWORD
    if not email or not password:
        email = input("ONES email: ")
        password = input("ONES password: ")

    result = api_request("POST", "/project/api/project/auth/login",
                         body={"email": email, "password": password},
                         host=host)
    token = result.get("token")
    user_id = result.get("uuid")
    team_uuid = result.get("user", {}).get("team_uuid") or \
                (result.get("teams", [{}])[0].get("uuid") if result.get("teams") else "")

    cfg = load_config()
    cfg.update({"host": host, "token": token, "user_id": user_id, "team_uuid": team_uuid,
                "email": email})
    save_config(cfg)
    print(f"Logged in as {result.get('name')} (user_id={user_id}, team={team_uuid})")
    return token, user_id, team_uuid


def list_spaces():
    host, token, user_id, team_uuid = get_credentials()
    if not token:
        print("Not logged in. Run: python ones_client.py login", file=sys.stderr)
        sys.exit(1)
    result = api_request("GET", f"/wiki/api/wiki/team/{team_uuid}/spaces",
                         token=token, user_id=user_id, host=host)
    spaces = result.get("spaces", result if isinstance(result, list) else [])
    print(f"{'UUID':<36}  {'Title'}")
    print("-" * 70)
    for s in spaces:
        print(f"{s.get('uuid', ''):<36}  {s.get('title', '')}")
    return spaces


def list_pages(space_uuid):
    host, token, user_id, team_uuid = get_credentials()
    result = api_request("GET",
                         f"/wiki/api/wiki/team/{team_uuid}/space/{space_uuid}/pages?status=normal",
                         token=token, user_id=user_id, host=host)
    pages = result.get("pages", result if isinstance(result, list) else [])
    print(f"{'UUID':<36}  {'Title'}")
    print("-" * 70)
    for p in pages:
        print(f"{p.get('uuid', ''):<36}  {p.get('title', '')}")
    return pages


def markdown_to_html(md_text):
    """Basic markdown to HTML conversion for ONES wiki."""
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
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
        # Inline code
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Links
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
        return text

    for line in lines:
        # Code block
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

        # Headings
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            close_list()
            level = len(m.group(1))
            html_lines.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue

        # Horizontal rule
        if re.match(r'^(-{3,}|_{3,}|\*{3,})$', line.strip()):
            close_list()
            html_lines.append("<hr/>")
            continue

        # Unordered list
        m = re.match(r'^[\-\*\+]\s+(.*)', line)
        if m:
            if not in_ul:
                close_list()
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # Ordered list
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            if not in_ol:
                close_list()
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # Blockquote
        m = re.match(r'^>\s*(.*)', line)
        if m:
            close_list()
            html_lines.append(f"<blockquote><p>{inline(m.group(1))}</p></blockquote>")
            continue

        # Empty line
        if not line.strip():
            close_list()
            html_lines.append("")
            continue

        # Paragraph
        close_list()
        html_lines.append(f"<p>{inline(line)}</p>")

    close_list()
    return "\n".join(html_lines)


def upload_page(md_file, space_uuid, parent_uuid=None, title=None):
    host, token, user_id, team_uuid = get_credentials()
    if not token:
        print("Not logged in. Run: python ones_client.py login", file=sys.stderr)
        sys.exit(1)

    md_path = Path(md_file)
    if not md_path.exists():
        print(f"File not found: {md_file}", file=sys.stderr)
        sys.exit(1)

    md_text = md_path.read_text(encoding="utf-8")
    title = title or md_path.stem.replace("-", " ").replace("_", " ").title()
    content = markdown_to_html(md_text)

    body = {
        "space_uuid": space_uuid,
        "parent_uuid": parent_uuid or "",
        "title": title,
        "content": content,
        "status": 1,
    }
    result = api_request("POST",
                         f"/wiki/api/wiki/team/{team_uuid}/space/{space_uuid}/pages/add",
                         body=body, token=token, user_id=user_id, host=host)
    page_uuid = result.get("uuid") or result.get("page", {}).get("uuid", "")
    print(f"Page created: {title}")
    print(f"  UUID: {page_uuid}")
    print(f"  URL: {host}/wiki/#/space/{space_uuid}/page/{page_uuid}")
    return result


def update_page(md_file, page_uuid):
    host, token, user_id, team_uuid = get_credentials()
    if not token:
        print("Not logged in. Run: python ones_client.py login", file=sys.stderr)
        sys.exit(1)

    md_path = Path(md_file)
    if not md_path.exists():
        print(f"File not found: {md_file}", file=sys.stderr)
        sys.exit(1)

    # Get current page to preserve space_uuid and version
    current = api_request("GET",
                           f"/wiki/api/wiki/team/{team_uuid}/page/{page_uuid}",
                           token=token, user_id=user_id, host=host)
    page = current.get("page", current)
    space_uuid = page.get("space_uuid", "")

    md_text = md_path.read_text(encoding="utf-8")
    title = md_path.stem.replace("-", " ").replace("_", " ").title()
    content = markdown_to_html(md_text)

    body = {
        "title": title,
        "content": content,
        "status": 1,
    }
    result = api_request("POST",
                         f"/wiki/api/wiki/team/{team_uuid}/page/{page_uuid}/update",
                         body=body, token=token, user_id=user_id, host=host)
    print(f"Page updated: {title}")
    print(f"  UUID: {page_uuid}")
    print(f"  URL: {host}/wiki/#/space/{space_uuid}/page/{page_uuid}")
    return result


def main():
    parser = argparse.ArgumentParser(description="ONES Wiki Client")
    sub = parser.add_subparsers(dest="cmd")

    # login
    p_login = sub.add_parser("login", help="Login and save credentials")
    p_login.add_argument("--email", default="")
    p_login.add_argument("--password", default="")

    # list-spaces
    sub.add_parser("list-spaces", help="List all wiki spaces")

    # list-pages
    p_lp = sub.add_parser("list-pages", help="List pages in a space")
    p_lp.add_argument("--space", required=True, help="Space UUID")

    # upload
    p_up = sub.add_parser("upload", help="Upload markdown file as new page")
    p_up.add_argument("file", help="Markdown file path")
    p_up.add_argument("--space", required=True, help="Space UUID")
    p_up.add_argument("--parent", default=None, help="Parent page UUID")
    p_up.add_argument("--title", default=None, help="Page title (default: filename)")

    # update
    p_ud = sub.add_parser("update", help="Update existing page from markdown file")
    p_ud.add_argument("file", help="Markdown file path")
    p_ud.add_argument("--page", required=True, help="Page UUID to update")

    args = parser.parse_args()

    if args.cmd == "login":
        login(args.email, args.password)
    elif args.cmd == "list-spaces":
        list_spaces()
    elif args.cmd == "list-pages":
        list_pages(args.space)
    elif args.cmd == "upload":
        upload_page(args.file, args.space, args.parent, args.title)
    elif args.cmd == "update":
        update_page(args.file, args.page)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
