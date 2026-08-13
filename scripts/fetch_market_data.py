"""Fetch daily market data for the Fund Research dashboard.

Three sources, all tolerant of failure (a bad day for one source never blocks
the others, and previous data is kept):

- Trustnet (FE fundinfo): resolves every fund ISIN currently held in a model
  to its Trustnet factsheet, then pulls the provider factsheet PDF link,
  cumulative performance vs the IA sector (with quartile rankings) and the
  risk ratios (Sharpe, volatility, alpha, beta).
- Financial Times: the latest article links for each macro theme (equity
  region / asset class), scraped from the public search pages. Links only -
  reading the articles needs an FT subscription.
- AI macro summary: a short bullet summary of the FT headlines, generated
  with the Claude Code CLI (claude -p) or the Anthropic API when
  ANTHROPIC_API_KEY is set. Macro only - no individual stocks.

Results land in data/market_data.json and are spliced into every dashboard
HTML copy between the live-market-data anchors (separate from the workbook
seed block, so this never touches the model weights).

Usage:
  python fetch_market_data.py                 full daily refresh
  python fetch_market_data.py --skip-tn       skip the Trustnet crawl
  python fetch_market_data.py --skip-ft       skip the FT article pull
  python fetch_market_data.py --skip-ai       keep the previous AI summary
  python fetch_market_data.py --isin XX       debug: one ISIN only, verbose
  python fetch_market_data.py --limit N       debug: first N ISINs only
"""
import datetime
import html as htmlmod
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(REPO, "data", "market_data.json")
HTML_MAIN = os.path.join(REPO, "lumin-portfolios.html")

MSTART = "  // ---------- live market data (Trustnet / FT) ----------"
MEND = "  // ---------- end live market data ----------"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TN = "https://www.trustnet.com"
FT = "https://www.ft.com"
DELAY = 0.35          # politeness gap between requests
TIMEOUT = 30

# One FT search per macro theme. Keys must match macroTheme() in the HTML.
FT_THEMES = [
    ("global",       "Global markets",            "global economy markets outlook"),
    ("uk",           "UK economy",                "UK economy inflation Bank of England"),
    ("us",           "US economy",                "US economy Federal Reserve inflation"),
    ("europe",       "Europe ex-UK",              "eurozone economy ECB"),
    ("em",           "Emerging markets",          "emerging markets economy"),
    ("japan",        "Japan",                     "Japan economy Bank of Japan"),
    ("asia",         "Asia Pacific",              "Asia Pacific economy markets"),
    ("specialist",   "Sectors & commodities",     "commodities infrastructure sectors outlook"),
    ("bonds",        "Bonds & rates",             "bond markets interest rates outlook"),
    ("diversifiers", "Alternatives & real assets", "gold infrastructure property alternative assets"),
    ("rates",        "Rates & cash",              "central banks interest rates cash"),
]


def log(msg):
    print(msg, flush=True)


def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def strip_tags(s):
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", s))


def to_num(s):
    s = str(s).strip().replace(",", "")
    if not s or s.lower() in ("n/a", "na", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------- fund universe

def active_isins(html_path):
    """ISINs held in the latest snapshot of any model, from the dashboard's
    own seed block - no workbook needed. The seed emitter writes SEED_FUNDS
    one JSON array per line, and each model's snapshots newest-first."""
    html = open(html_path, encoding="utf-8").read()

    m = re.search(r"var SEED_FUNDS = \[\n(.*?)\n  \];", html, re.S)
    if not m:
        raise SystemExit("SEED_FUNDS not found in " + html_path)
    funds = []
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if line.startswith("["):
            funds.append(json.loads(line))

    m = re.search(r"var SEED_MODELS = \[\n(.*?)\n  \];", html, re.S)
    if not m:
        raise SystemExit("SEED_MODELS not found in " + html_path)
    active = set()
    expect_first_snap = False
    for line in m.group(1).splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith(",["):        # model start
            expect_first_snap = True
        elif expect_first_snap and s.startswith("["):     # newest snapshot
            snap = json.loads(s.rstrip(","))
            for fund_idx, _w in snap[1]:
                active.add(fund_idx)
            expect_first_snap = False

    out = []
    for i in sorted(active):
        name, isin, _cls = funds[i]
        if isin and re.match(r"^[A-Z]{2}[A-Z0-9]{9}\d$", isin):
            out.append((isin, name))
    return out


# ---------------------------------------------------------------- Trustnet

class Trustnet:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.token = None

    def _get(self, url, **kw):
        time.sleep(DELAY)
        r = self.s.get(url, timeout=TIMEOUT, **kw)
        r.raise_for_status()
        return r.text

    def open_session(self):
        """Prime cookies + the anti-forgery token the search POST needs."""
        page = self._get(TN + "/")
        m = re.search(r'__RequestVerificationToken[^>]*value="([^"]+)"', page)
        if not m:
            raise RuntimeError("no anti-forgery token on trustnet.com")
        self.token = m.group(1)

    def search(self, isin):
        """ISIN -> (universe, citicode, slug) of the first fund result."""
        time.sleep(DELAY)
        r = self.s.post(
            TN + "/umbraco/surface/search/SearchAdvanceFund",
            data={"Keywords": isin, "FundUniverse": "U",
                  "__RequestVerificationToken": self.token},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": TN + "/"},
            timeout=TIMEOUT)
        r.raise_for_status()
        m = re.search(r'href="/factsheets/([A-Za-z])/([A-Za-z0-9]+)/([a-z0-9-]+)"', r.text)
        if not m:
            return None
        return m.group(1).upper(), m.group(2).upper(), m.group(3)

    def component(self, page_url, page_id, key):
        return self._get(
            TN + "/Umbraco/Surface/ComponentRenderer/RenderGridComponent"
            "?pageId=" + page_id + "&componentKey=" + key,
            headers={"Referer": page_url})

    @staticmethod
    def _rows(fragment):
        """<tr> rows as lists of stripped cell texts."""
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", fragment, re.S):
            cells = [" ".join(strip_tags(c).split())
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if cells:
                rows.append(cells)
        return rows

    def fund(self, isin):
        """Everything the dashboard needs for one ISIN."""
        hit = self.search(isin)
        if not hit:
            return None, "no Trustnet result for this ISIN"
        universe, citicode, slug = hit
        page_url = TN + "/factsheets/%s/%s/%s" % (universe.lower(), citicode.lower(), slug)
        page = self._get(page_url)

        entry = {
            "u": universe, "cc": citicode, "url": page_url,
            "asOf": datetime.date.today().isoformat(),
        }

        m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        if m:
            entry["name"] = " ".join(strip_tags(m.group(1)).split())

        # Provider factsheet / KIID PDFs live on FE's documents CDN, which
        # allows embedding - store the direct PDF URL, not the viewer page
        # (whose path varies: /Factsheet-PDF, /PDFAd, ...).
        for pdf, doc in re.findall(
                r'[?&]pdf=([^&"\']+)[^"\']*?document=([A-Za-z]+)',
                page):
            url = urllib.parse.unquote(pdf)
            if doc == "ProviderFactsheetURL" and "pdf" not in entry:
                entry["pdf"] = url
            elif doc.upper().startswith("KIID") and "kiid" not in entry:
                entry["kiid"] = url

        def component_of(cls):
            m = re.search(cls + r'[^>]*data-component-key="([^"]+)" data-page-id="(\d+)"', page)
            return m and self.component(page_url, m.group(2), m.group(1))

        # Cumulative performance: fund row, sector row, quartile row.
        # The component class varies by page template (with/without "fund").
        cum = component_of("fe_cmp_(?:fund)?cumulativedataperformance")
        if cum:
            periods = ["p3m", "p6m", "p1y", "p3y", "p5y"]
            data_rows = [r for r in self._rows(cum) if len(r) >= 6]
            fund_row = sector_row = quart_row = None
            for r in data_rows:
                label = r[0].lower()
                if label.startswith("time period") or label == "key":
                    continue
                if label.startswith("position"):
                    continue
                if label.startswith("quartile"):
                    quart_row = r
                elif fund_row is None:
                    fund_row = r
                elif sector_row is None:
                    sector_row = r
            if fund_row:
                entry["perf"] = dict(zip(periods, [to_num(v) for v in fund_row[1:6]]))
            if sector_row:
                entry["sector"] = sector_row[0]
                entry["sectorPerf"] = dict(zip(periods, [to_num(v) for v in sector_row[1:6]]))
            if quart_row:
                qs = [int(v) if str(v).strip().isdigit() else None for v in quart_row[1:6]]
                entry["quartiles"] = dict(zip(periods, qs))

        # Ratio information: 1y / 3y columns.
        ratio = component_of("fe_cmp_fundratioinformation")
        if ratio:
            ratios = {}
            for r in self._rows(ratio):
                if len(r) < 3:
                    continue
                label = r[0].lower()
                y1, y3 = to_num(r[1]), to_num(r[2])
                if label.startswith("volatility"):
                    ratios["vol1y"], ratios["vol3y"] = y1, y3
                elif label.startswith("sharpe"):
                    ratios["sharpe1y"], ratios["sharpe3y"] = y1, y3
                elif label.startswith("alpha"):
                    ratios["alpha3y"] = y3
                elif label.startswith("beta"):
                    ratios["beta3y"] = y3
            if ratios:
                entry["ratios"] = ratios

        if "perf" not in entry and "pdf" not in entry:
            return None, "Trustnet page had no performance table or factsheet"
        return entry, None


def fetch_trustnet(isins, previous):
    tn = Trustnet()
    tn.open_session()
    out, errors = dict(previous), {}
    for n, (isin, name) in enumerate(isins, 1):
        try:
            entry, err = tn.fund(isin)
        except Exception as e:            # network blip: keep yesterday's entry
            entry, err = None, str(e)
        if entry:
            out[isin] = entry
            log("  [%d/%d] %s  %s ok" % (n, len(isins), isin, name[:44]))
        else:
            errors[isin] = err
            log("  [%d/%d] %s  %s FAILED: %s" % (n, len(isins), isin, name[:36], err))
    return out, errors


# ---------------------------------------------------------------- FT articles

FT_DELAY = 12   # ft.com rate-limits rapid searching - space the 11 queries out


def fetch_ft():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    themes = {}
    for n, (key, label, query) in enumerate(FT_THEMES):
        if n:
            time.sleep(FT_DELAY)
        r = None
        for attempt in (1, 2):
            try:
                r = s.get(FT + "/search",
                          params={"q": query, "dateRange": "now-14d"}, timeout=TIMEOUT)
                r.raise_for_status()
                break
            except Exception as e:
                r = None
                if attempt == 1:
                    time.sleep(45)   # a 429 clears after a pause
                else:
                    log("  FT %s FAILED: %s" % (key, e))
        if r is None:
            continue
        # Headlines inside the search-results region only.
        page = r.text
        start = page.find('class="search-results')
        region = page[start:] if start > 0 else page
        arts, seen = [], set()
        for m in re.finditer(
                r'o-teaser__heading[^>]*>\s*<a[^>]*href="(https://www\.ft\.com/content/[^"]+)"[^>]*>(.*?)</a>',
                region, re.S):
            url = m.group(1)
            title = " ".join(strip_tags(m.group(2)).split())
            if url in seen or not title:
                continue
            seen.add(url)
            tm = re.search(r'dateTime="([^"]+)"', region[m.end():m.end() + 1500])
            date = tm.group(1)[:10] if tm else ""
            arts.append([title, url, date])
            if len(arts) >= 6:
                break
        themes[key] = {"label": label, "query": query, "articles": arts}
        log("  FT %s: %d articles" % (key, len(arts)))
    return themes


# ---------------------------------------------------------------- AI summary

AI_PROMPT = """You are writing the daily macro briefing for a UK wealth manager's internal fund-research dashboard.

Below are recent Financial Times headlines grouped by market theme. Using them (plus general macro context), write 6 to 8 short bullet points giving a holistic view of what has been happening in the macro environment: growth, inflation, central banks and rates, bond and equity markets by region, currencies and commodities where relevant.

Rules:
- Macro only. Never mention individual companies, stocks or funds.
- Each bullet is one plain sentence, no more than 25 words, no jargon a client-facing adviser would not use.
- No introduction, no conclusion, no markdown headers.
- Output exactly one bullet per line, each line starting with "- ".

Headlines:
%s"""


def build_ai_prompt(themes):
    lines = []
    for key, data in themes.items():
        if not data.get("articles"):
            continue
        lines.append(data["label"] + ":")
        for title, _url, date in data["articles"]:
            lines.append("  - %s (%s)" % (title, date or "recent"))
    return AI_PROMPT % "\n".join(lines)


def generate_summary(themes):
    """Bullets via the Anthropic API when a key is configured, else the local
    Claude Code CLI (uses the developer's existing login). Returns None on
    failure so the previous summary is kept."""
    prompt = build_ai_prompt(themes)

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model="claude-opus-5", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}])
            if resp.stop_reason == "refusal":
                raise RuntimeError("model declined the request")
            text = "".join(b.text for b in resp.content if b.type == "text")
            return parse_bullets(text, "anthropic-api")
        except Exception as e:
            log("  AI summary via API failed: %s" % e)

    claude = shutil.which("claude") or next(
        (p for p in (os.path.expanduser("~/.local/bin/claude.exe"),
                     os.path.expanduser("~/.local/bin/claude"))
         if os.path.exists(p)), None)
    if claude:
        try:
            r = subprocess.run(
                [claude, "-p", "--output-format", "text"],
                input=prompt, capture_output=True, text=True,
                encoding="utf-8", timeout=300)
            if r.returncode != 0:
                raise RuntimeError((r.stderr or "").strip()[:200] or "claude CLI error")
            return parse_bullets(r.stdout, "claude-cli")
        except Exception as e:
            log("  AI summary via claude CLI failed: %s" % e)
    else:
        log("  no ANTHROPIC_API_KEY and no claude CLI - keeping previous summary")
    return None


def parse_bullets(text, source):
    bullets = [ln.strip()[2:].strip() for ln in text.splitlines()
               if ln.strip().startswith("- ")]
    bullets = [b for b in bullets if b]
    if not (4 <= len(bullets) <= 12):
        log("  AI summary discarded - got %d bullets" % len(bullets))
        return None
    return {"generatedAt": now_stamp(), "source": source, "bullets": bullets}


# ---------------------------------------------------------------- splice

def targets():
    """Reuse the workbook refresher's target list (repo copy + any synced
    SharePoint copies)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import refresh_dashboard
    return refresh_dashboard.targets()


def emit_block(data):
    def j(o):
        return json.dumps(o, ensure_ascii=False, separators=(",", ":"))

    tn = data.get("tn", {})
    meta = {"fetchedAt": data.get("fetchedAt", ""), "funds": len(tn),
            "errors": len(data.get("tnErrors", {}))}
    macro = {"fetchedAt": data.get("fetchedAt", ""),
             "themes": data.get("themes", {}),
             "summary": data.get("summary")}

    b = io.StringIO()
    b.write(MSTART + "\n")
    b.write("  // Written daily by scripts/fetch_market_data.py - do not edit by hand.\n")
    b.write("  var SEED_TN = " + j(tn) + ";\n")
    b.write("  var SEED_TN_META = " + j(meta) + ";\n")
    b.write("  var SEED_MACRO = " + j(macro) + ";\n")
    b.write(MEND)
    return b.getvalue()


def splice(target, block):
    html = open(target, encoding="utf-8").read()
    i = html.find(MSTART)
    k = html.find(MEND)
    if i < 0 or k < 0 or k <= i:
        log("  anchors not found in %s - skipped" % target)
        return False
    html = html[:i] + block + html[k + len(MEND):]
    open(target, "w", encoding="utf-8").write(html)
    return True


# ---------------------------------------------------------------- main

def main():
    argv = sys.argv[1:]
    skip_tn = "--skip-tn" in argv
    skip_ft = "--skip-ft" in argv
    skip_ai = "--skip-ai" in argv
    no_splice = "--no-splice" in argv
    only_isin = limit = None
    if "--isin" in argv:
        only_isin = argv[argv.index("--isin") + 1].upper()
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])

    previous = {}
    if os.path.exists(DATA_PATH):
        try:
            previous = json.load(open(DATA_PATH, encoding="utf-8"))
        except ValueError:
            previous = {}

    data = {
        "fetchedAt": now_stamp(),
        "tn": previous.get("tn", {}),
        "tnErrors": previous.get("tnErrors", {}),
        "themes": previous.get("themes", {}),
        "summary": previous.get("summary"),
    }

    if not skip_tn:
        isins = active_isins(HTML_MAIN)
        if only_isin:
            isins = [x for x in isins if x[0] == only_isin]
        if limit:
            isins = isins[:limit]
        log("Trustnet: %d funds" % len(isins))
        data["tn"], data["tnErrors"] = fetch_trustnet(isins, data["tn"])

    if not skip_ft:
        log("FT articles:")
        # Merge per theme, so one rate-limited query keeps yesterday's links.
        for key, theme in fetch_ft().items():
            if theme["articles"] or key not in data["themes"]:
                data["themes"][key] = theme

    if not skip_ai and data["themes"]:
        log("AI macro summary:")
        summary = generate_summary(data["themes"])
        if summary:
            data["summary"] = summary
            log("  %d bullets via %s" % (len(summary["bullets"]), summary["source"]))

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    log("saved " + DATA_PATH)

    if not no_splice:
        block = emit_block(data)
        for t in targets():
            if os.path.exists(t) and splice(t, block):
                log("updated %s" % t)

    covered = len(data["tn"])
    log("done: %d funds on Trustnet, %d errors, %d FT themes, summary %s"
        % (covered, len(data["tnErrors"]), len(data["themes"]),
           "fresh" if data.get("summary") else "missing"))


if __name__ == "__main__":
    main()
