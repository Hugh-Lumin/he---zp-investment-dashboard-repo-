"""Maintain data/notes_map.json - fund ISIN -> manager-notes folder links.

The map used to store machine-specific local paths (C:\\Users\\<someone>\\...).
This script converts every entry to the folder's SharePoint web URL on the
Investment Team site, so links work for the whole team from any machine, and
the dashboard opens them straight in the browser.

It also rescans the locally synced 'Investment team work' folder (if present)
to refresh file counts and report NEW fund folders that aren't in the map yet.

Usage:  python build_notes_map.py            convert + rescan + report
        python build_notes_map.py --dry-run  show what would change, write nothing
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parent.parent
NOTES_PATH = REPO / "data" / "notes_map.json"
HOME = Path(os.path.expanduser("~"))

# 'Investment team work' is a synced shortcut to this Investment Team site
# folder (see the matching constants in lumin-portfolios.html).
TEAM_HOST = "https://luminwealthmanagement.sharepoint.com"
TEAM_SITE = "/sites/LWMInvestmentTeam"
TEAM_ROOT = TEAM_SITE + "/Shared Documents/Research/Manager Meeting Notes/"
LOCAL_MARKER = "investment team work"


def folder_web_url(rel):
    """Relative folder path under Manager Meeting Notes -> library view URL,
    mirroring fileUrl() in lumin-portfolios.html."""
    server_rel = TEAM_ROOT + rel.replace("\\", "/")
    return (TEAM_HOST + TEAM_SITE + "/Shared%20Documents/Forms/AllItems.aspx?id="
            + quote(server_rel, safe="-_.!~*'()"))


def to_rel(local_path):
    """Local synced path -> path relative to the Manager Meeting Notes root."""
    p = str(local_path).replace("/", "\\")
    low = p.lower()
    i = low.find(LOCAL_MARKER)
    if i < 0:
        return None
    return p[i + len(LOCAL_MARKER):].lstrip("\\")


def local_root():
    """The synced 'Investment team work' folder on this machine, if any."""
    for root in ("OneDrive - Lumin Wealth Management", "Lumin Wealth Management"):
        cand = HOME / root / "Investment team work"
        if cand.is_dir():
            return cand
    return None


def file_count(folder):
    return sum(1 for p in folder.rglob("*") if p.is_file() and not p.name.startswith("~$"))


def main():
    dry = "--dry-run" in sys.argv
    notes = json.loads(NOTES_PATH.read_text(encoding="utf-8"))

    converted = kept = 0
    for isin, entries in notes.items():
        for e in entries:
            path = e["path"]
            if path.lower().startswith("http"):
                kept += 1
                continue
            rel = to_rel(path)
            if rel is None:
                print("UNRESOLVED (left as-is): %s" % path)
                kept += 1
                continue
            e["path"] = folder_web_url(rel)
            e["rel"] = rel.replace("\\", "/")
            converted += 1

    root = local_root()
    refreshed = 0
    unmapped = []
    if root:
        mapped_rels = {e.get("rel", "").lower() for es in notes.values() for e in es}
        for isin, entries in notes.items():
            for e in entries:
                rel = e.get("rel")
                if not rel:
                    continue
                folder = root / rel.replace("/", "\\")
                if folder.is_dir():
                    n = file_count(folder)
                    if n != e.get("count"):
                        e["count"] = n
                        refreshed += 1
                else:
                    print("MISSING on disk (folder moved/renamed?): %s" % rel)
        # fund-note folders on disk that no map entry points at
        for sub in sorted(root.iterdir()):
            if not sub.is_dir():
                continue
            for fund_dir in sorted(sub.iterdir()):
                if not fund_dir.is_dir():
                    continue
                rel = "%s/%s" % (sub.name, fund_dir.name)
                if rel.lower() not in mapped_rels:
                    unmapped.append(rel)
    else:
        print("note: no synced 'Investment team work' folder on this machine - "
              "counts not refreshed, new folders not detected")

    print("entries converted to web URLs: %d | already URLs/kept: %d | counts refreshed: %d"
          % (converted, kept, refreshed))
    if unmapped:
        print("\nNEW folders with no dashboard link yet (add to notes_map.json):")
        for r in unmapped:
            print("   -", r)

    if dry:
        print("(dry run - nothing written)")
        return
    NOTES_PATH.write_text(json.dumps(notes, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote %s" % NOTES_PATH)
    print("Now run refresh_dashboard.py so the dashboard picks up the new links.")


if __name__ == "__main__":
    main()
