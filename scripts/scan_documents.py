"""Scan the Investment Team SharePoint site for dashboard documents.

Produces data/documents_index.json (seeded into the dashboard as SEED_DOCS -
the read-only "On SharePoint" listings per section) and refreshes
data/notes_map.json (fund manager-notes folders: live file counts, web URLs,
and new-folder mapping suggestions from the fund register).

Folders scanned per section come from data/sources.json:
    { "qir": { "folder": "Research/Quarterly Investment Reviews", "recurse": true }, ... }
Paths are relative to the team site's default document library
(Shared Documents). A section absent from sources.json is left alone.

Credentials (Graph API, client credentials flow) come from env vars:
    SP_TENANT_ID, SP_CLIENT_ID, SP_CLIENT_SECRET
- the same app registration the data-zentrum pipeline uses
('SharepointConnector'). Fetch them from AWS Secrets Manager (AWSSecrets:
sharepoint_tenant_id / sharepoint_client_id / sharepoint_secret_value).

Usage:
    python scripts/scan_documents.py                scan + write both files
    python scripts/scan_documents.py --discover     list the site's top folders and exit
    python scripts/scan_documents.py --dry-run      print what would change, write nothing

Run refresh_dashboard.py afterwards so the dashboard picks the new data up.
"""
import datetime
import json
import os
import re
import sys
from urllib.parse import quote

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_PATH = os.path.join(REPO, "data", "sources.json")
DOCS_PATH = os.path.join(REPO, "data", "documents_index.json")
NOTES_PATH = os.path.join(REPO, "data", "notes_map.json")
FACTS_PATH = os.path.join(REPO, "data", "funds.json")

GRAPH = "https://graph.microsoft.com/v1.0"
HOST = "luminwealthmanagement.sharepoint.com"
SITE = "LWMInvestmentTeam"

TEAM_HOST = "https://luminwealthmanagement.sharepoint.com"
TEAM_SITE = "/sites/LWMInvestmentTeam"
NOTES_ROOT = "Research/Manager Meeting Notes"
NOTES_SERVER_ROOT = TEAM_SITE + "/Shared Documents/" + NOTES_ROOT + "/"

# Files that are workings, not documents to surface.
SKIP_FILE = re.compile(r"^(~\$|Thumbs\.db$|desktop\.ini$)", re.I)


def token():
    for var in ("SP_TENANT_ID", "SP_CLIENT_ID", "SP_CLIENT_SECRET"):
        if not os.environ.get(var):
            sys.exit("missing env var %s - see the docstring for where the "
                     "credentials come from" % var)
    resp = requests.post(
        "https://login.microsoftonline.com/%s/oauth2/v2.0/token"
        % os.environ["SP_TENANT_ID"],
        data={
            "client_id": os.environ["SP_CLIENT_ID"],
            "client_secret": os.environ["SP_CLIENT_SECRET"],
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get(url, tok):
    resp = requests.get(url, headers={"Authorization": "Bearer " + tok})
    resp.raise_for_status()
    return resp.json()


def get_site_id(tok):
    return get("%s/sites/%s:/sites/%s" % (GRAPH, HOST, SITE), tok)["id"]


def children(tok, site_id, path):
    """All child items of a folder path on the site's default drive."""
    enc = quote(path)
    url = "%s/sites/%s/drive/root:/%s:/children?$top=200" % (GRAPH, site_id, enc)
    items = []
    while url:
        page = get(url, tok)
        items.extend(page.get("value", []))
        url = page.get("@odata.nextLink")
    return items


def walk_files(tok, site_id, path, recurse, depth=3):
    """[(item, relative folder)] for files under path."""
    out = []
    for item in children(tok, site_id, path):
        name = item.get("name", "")
        if "file" in item:
            if not SKIP_FILE.match(name):
                out.append((item, ""))
        elif "folder" in item and recurse and depth > 1:
            for sub, rel in walk_files(tok, site_id, path + "/" + name,
                                       recurse, depth - 1):
                out.append((sub, (name + "/" + rel).rstrip("/")))
    return out


def scan_sections(tok, site_id, sources):
    sections = {}
    for key, cfg in sources.items():
        folder = cfg.get("folder", "")
        if not folder:
            continue
        try:
            found = walk_files(tok, site_id, folder,
                               cfg.get("recurse", True))
        except requests.HTTPError as exc:
            print("WARNING: section '%s' folder '%s' not readable: %s"
                  % (key, folder, exc))
            continue
        docs = []
        for item, rel in found:
            docs.append({
                "title": item["name"],
                "url": item.get("webUrl", ""),
                "modified": (item.get("lastModifiedDateTime") or "")[:10],
                "folder": rel,
            })
        docs.sort(key=lambda d: d["modified"], reverse=True)
        sections[key] = docs
        print("section %-10s %s: %d documents" % (key, folder, len(docs)))
    return sections


# ------------------------------------------------------------ notes map

def folder_web_url(rel):
    server_rel = NOTES_SERVER_ROOT + rel.replace("\\", "/")
    return (TEAM_HOST + TEAM_SITE + "/Shared%20Documents/Forms/AllItems.aspx?id="
            + quote(server_rel, safe="-_.!~*'()"))


def count_files(tok, site_id, path, depth=3):
    total = 0
    for item in children(tok, site_id, path):
        if "file" in item:
            if not SKIP_FILE.match(item.get("name", "")):
                total += 1
        elif "folder" in item and depth > 1:
            total += count_files(tok, site_id, path + "/" + item["name"], depth - 1)
    return total


def scan_note_folders(tok, site_id):
    """{'Equities/Artemis Global EM': file count, ...} live from Graph."""
    counts = {}
    for class_dir in children(tok, site_id, NOTES_ROOT):
        if "folder" not in class_dir:
            continue
        cls = class_dir["name"]
        for fund_dir in children(tok, site_id, NOTES_ROOT + "/" + cls):
            if "folder" not in fund_dir:
                continue
            rel = cls + "/" + fund_dir["name"]
            counts[rel] = count_files(tok, site_id, NOTES_ROOT + "/" + rel)
    return counts


def norm_tokens(s):
    stop = {"fund", "funds", "the", "of", "and", "trust", "plc", "ucits",
            "etf", "index", "class", "acc", "inc"}
    toks = re.findall(r"[a-z0-9&]+", str(s).lower())
    return [t for t in toks if t not in stop]


def suggest_fund(rel, funds):
    """Match a new folder name to exactly one register fund, or None.
    Confident = every folder token appears in one and only one fund name."""
    folder_name = rel.split("/", 1)[-1]
    toks = norm_tokens(folder_name)
    if not toks:
        return None
    hits = []
    for f in funds:
        name_toks = set(norm_tokens(f["name"]))
        if all(t in name_toks for t in toks):
            hits.append(f)
    return hits[0] if len(hits) == 1 else None


def refresh_notes(notes, live_counts, funds):
    """Update counts/urls in place; auto-map confident new folders; return
    (unmapped, missing, added) lists for the report."""
    mapped = {}
    for isin, entries in notes.items():
        for e in entries:
            if e.get("rel"):
                mapped.setdefault(e["rel"].lower(), []).append(e)

    missing = []
    for rel_lower, entries in mapped.items():
        live = next((v for k, v in live_counts.items() if k.lower() == rel_lower), None)
        if live is None:
            missing.append(entries[0]["rel"])
            continue
        for e in entries:
            e["count"] = live
            e["path"] = folder_web_url(e["rel"])

    unmapped, added = [], []
    for rel in sorted(live_counts):
        if rel.lower() in mapped:
            continue
        fund = suggest_fund(rel, funds)
        if fund:
            label = rel.split("/", 1)[-1]
            entry = {"label": label, "path": folder_web_url(rel),
                     "count": live_counts[rel], "rel": rel}
            n = 0
            for sc in fund.get("shareClasses", []):
                if sc.get("isin"):
                    notes.setdefault(sc["isin"], []).append(dict(entry))
                    n += 1
            if n:
                added.append("%s -> %s (%d share class%s)"
                             % (rel, fund["name"], n, "" if n == 1 else "es"))
            else:
                unmapped.append(rel)
        else:
            unmapped.append(rel)
    return unmapped, missing, added


def main():
    discover = "--discover" in sys.argv
    dry = "--dry-run" in sys.argv

    tok = token()
    site_id = get_site_id(tok)
    print("site id:", site_id.split(",")[1] if "," in site_id else site_id)

    if discover:
        print("\nTop-level folders on the default library:")
        for item in children(tok, site_id, ""):
            if "folder" in item:
                print("  %-40s %5d items" % (item["name"],
                                             item["folder"].get("childCount", 0)))
        print("\n'Research' subfolders:")
        try:
            for item in children(tok, site_id, "Research"):
                if "folder" in item:
                    print("  Research/%-31s %5d items"
                          % (item["name"], item["folder"].get("childCount", 0)))
        except requests.HTTPError:
            print("  (no Research folder)")
        return

    sources = (json.load(open(SOURCES_PATH, encoding="utf-8"))
               if os.path.exists(SOURCES_PATH) else {})
    if not sources:
        print("note: %s missing or empty - no section scans" % SOURCES_PATH)

    sections = scan_sections(tok, site_id, sources)
    docs_out = {
        "scannedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sections": sections,
    }

    print("\nScanning %s..." % NOTES_ROOT)
    live_counts = scan_note_folders(tok, site_id)
    print("  %d fund folders live" % len(live_counts))

    notes = (json.load(open(NOTES_PATH, encoding="utf-8"))
             if os.path.exists(NOTES_PATH) else {})
    facts = (json.load(open(FACTS_PATH, encoding="utf-8"))
             if os.path.exists(FACTS_PATH) else {})
    unmapped, missing, added = refresh_notes(
        notes, live_counts, facts.get("funds", []))

    if added:
        print("\nAuto-mapped new folders (register match was unambiguous):")
        for a in added:
            print("   +", a)
    if unmapped:
        print("\nFolders with no fund mapping (add to notes_map.json by hand):")
        for r in unmapped:
            print("   -", r)
    if missing:
        print("\nMapped folders MISSING on SharePoint (moved/renamed? links kept):")
        for r in missing:
            print("   -", r)

    if dry:
        print("\n(dry run - nothing written)")
        return

    json.dump(docs_out, open(DOCS_PATH, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print("\nwrote %s" % DOCS_PATH)
    json.dump(notes, open(NOTES_PATH, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print("wrote %s" % NOTES_PATH)
    print("Now run refresh_dashboard.py so the dashboard picks the new data up.")


if __name__ == "__main__":
    main()
