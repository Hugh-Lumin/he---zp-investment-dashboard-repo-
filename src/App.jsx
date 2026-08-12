import { useEffect, useMemo, useState } from "react";
import {
  LayoutDashboard, Briefcase, PieChart, CalendarDays, Search, ExternalLink,
  ChevronLeft, Plus, Trash2, Phone, Mail, MessageSquare, Globe, FileText, Users, X,
} from "lucide-react";
import fundsData from "../data/funds.json";

const RANGE_COLOURS = {
  Core: "bg-blue-50 text-blue-700 border-blue-200",
  Passive: "bg-slate-100 text-slate-600 border-slate-300",
  ESG: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Income: "bg-amber-50 text-amber-700 border-amber-200",
};
const ASSET_COLOURS = {
  Equities: "bg-blue-50 text-blue-700 border-blue-200",
  "Fixed Interest": "bg-emerald-50 text-emerald-700 border-emerald-200",
  Diversifiers: "bg-amber-50 text-amber-700 border-amber-200",
  Cash: "bg-cyan-50 text-cyan-700 border-cyan-200",
};
const MGMT_COLOURS = {
  Active: "bg-violet-50 text-violet-700 border-violet-200",
  Passive: "bg-slate-100 text-slate-600 border-slate-300",
};
const REGIONS = ["UK", "US", "Europe", "Japan", "Asia & EM", "Global"];
const REGION_COLOURS = {
  UK: "bg-rose-50 text-rose-700 border-rose-200",
  US: "bg-indigo-50 text-indigo-700 border-indigo-200",
  Europe: "bg-sky-50 text-sky-700 border-sky-200",
  Japan: "bg-red-50 text-red-700 border-red-200",
  "Asia & EM": "bg-orange-50 text-orange-700 border-orange-200",
  Global: "bg-teal-50 text-teal-700 border-teal-200",
};
const COMM_TYPES = ["Meeting", "Email", "Call", "Note"];
const COMM_COLOURS = {
  Email: "bg-blue-50 text-blue-700 border-blue-200",
  Call: "bg-teal-50 text-teal-700 border-teal-200",
  Meeting: "bg-pink-50 text-pink-700 border-pink-200",
  Note: "bg-slate-50 text-slate-600 border-slate-200",
};

const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const today = () => new Date().toISOString().slice(0, 10);
const pct = (v, dp = 2) => (v === null || v === undefined || v === "" ? null : `${(Number(v) * 100).toFixed(dp)}%`);
const ftLink = (isin) => `https://markets.ft.com/data/funds/tearsheet/summary?s=${isin}`;

// Local persistence (per browser) until a shared backend is added
const load = (key, fallback) => {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
};
const save = (key, val) => { try { localStorage.setItem(key, JSON.stringify(val)); } catch { /* ignore */ } };

const commsKey = (fundName) => `comms:${fundName}`;
const loadComms = (fundName) => load(commsKey(fundName), []);

const Badge = ({ children, cls }) => (
  <span className={`text-xs px-2 py-0.5 rounded-full border whitespace-nowrap ${cls || "bg-slate-50 text-slate-600 border-slate-200"}`}>{children}</span>
);

function ConfirmDelete({ onConfirm }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <button
      onClick={(e) => { e.stopPropagation(); armed ? (setArmed(false), onConfirm()) : setArmed(true); }}
      title={armed ? "Click again to permanently delete" : "Delete"}
      className={armed ? "text-xs font-semibold bg-red-600 text-white rounded-full px-2 py-0.5 hover:bg-red-700 shrink-0" : "text-slate-300 hover:text-red-500 shrink-0"}>
      {armed ? "Confirm?" : <Trash2 size={14} />}
    </button>
  );
}

export default function App() {
  const [tab, setTab] = useState("funds");
  const [selected, setSelected] = useState(null);
  const [initials, setInitials] = useState(() => load("user-initials", ""));
  const funds = fundsData.funds;

  const saveInitials = (v) => {
    const up = v.toUpperCase().slice(0, 4);
    setInitials(up);
    save("user-initials", up);
  };

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, soon: true },
    { id: "funds", label: "Funds", icon: Briefcase },
    { id: "meetings", label: "Meetings", icon: CalendarDays },
    { id: "portfolios", label: "Portfolios", icon: PieChart, soon: true },
  ];

  const selectedFund = funds.find((f) => f.name === selected);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900" style={{ fontFamily: "ui-sans-serif, system-ui" }}>
      <header className="bg-slate-900 text-white px-6 py-4">
        <div className="flex items-start justify-between gap-4 flex-wrap max-w-6xl mx-auto">
          <div>
            <h1 className="text-lg font-semibold flex items-center gap-2">
              Fund Research Dashboard
              <span className="text-xs font-normal bg-slate-800 border border-slate-700 rounded-full px-2 py-0.5 flex items-center gap-1 text-slate-300">
                <Users size={11} /> Lumin investment team
              </span>
            </h1>
            <p className="text-slate-400 text-sm">
              Fund register from model book, effective {fundsData.effectiveDate} · data generated {fundsData.generatedAt}
            </p>
          </div>
          <label className="text-xs text-slate-300 flex items-center gap-1.5">Your initials
            <input value={initials} onChange={(e) => saveInitials(e.target.value)} placeholder="e.g. HE" maxLength={4}
              className="w-14 text-sm text-slate-900 rounded px-2 py-1 bg-white" />
          </label>
        </div>
      </header>

      <nav className="bg-white border-b border-slate-200 px-4">
        <div className="flex gap-1 overflow-x-auto max-w-6xl mx-auto">
          {tabs.map((t) => (
            <button key={t.id} disabled={t.soon}
              onClick={() => { setTab(t.id); setSelected(null); }}
              title={t.soon ? "Coming soon" : undefined}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${
                tab === t.id ? "border-slate-900 text-slate-900"
                : t.soon ? "border-transparent text-slate-300 cursor-not-allowed"
                : "border-transparent text-slate-500 hover:text-slate-800"}`}>
              <t.icon size={16} /> {t.label}
              {t.soon && <span className="text-[10px] uppercase tracking-wide bg-slate-100 rounded px-1 py-0.5">soon</span>}
            </button>
          ))}
        </div>
      </nav>

      <main className="p-6 max-w-6xl mx-auto">
        {selectedFund
          ? <FundPage fund={selectedFund} by={initials || "??"} onBack={() => setSelected(null)} />
          : tab === "meetings"
          ? <MeetingsTab funds={funds} onOpen={(f) => { setTab("funds"); setSelected(f.name); }} />
          : <FundList funds={funds} onOpen={(f) => setSelected(f.name)} />}
      </main>

      <footer className="px-6 py-4 text-xs text-slate-400 max-w-6xl mx-auto">
        Fund data extracted from the Model Portfolio Analysis workbook (run "npm run extract" after each rebalance to refresh).
        Communications are stored locally in this browser for now. Never enter client personal data.
      </footer>
    </div>
  );
}

function FundList({ funds, onOpen }) {
  const [q, setQ] = useState("");
  const [range, setRange] = useState("All");
  const [asset, setAsset] = useState("All");
  const [region, setRegion] = useState("All");
  const [mgmt, setMgmt] = useState("All");
  const [commCounts, setCommCounts] = useState({});

  useEffect(() => {
    const counts = {};
    for (const f of funds) counts[f.name] = loadComms(f.name).length;
    setCommCounts(counts);
  }, [funds]);

  const list = useMemo(() => funds.filter((f) =>
    (range === "All" || f.ranges.includes(range)) &&
    (asset === "All" || f.assetClass === asset) &&
    (region === "All" || f.region === region) &&
    (mgmt === "All" || f.mgmt === mgmt) &&
    (!q.trim() || (f.name + " " + f.house + " " + f.shareClasses.map((c) => c.isin).join(" ")).toLowerCase().includes(q.trim().toLowerCase()))
  ), [funds, q, range, asset, region, mgmt]);

  const rangeCount = (r) => funds.filter((f) => f.ranges.includes(r)).length;

  return (
    <div>
      <div className="flex justify-between items-center flex-wrap gap-3 mb-1">
        <h2 className="text-lg font-semibold">Funds ({list.length}{list.length !== funds.length ? ` of ${funds.length}` : ""})</h2>
        <div className="relative">
          <Search size={15} className="absolute left-2.5 top-2.5 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, house or ISIN"
            className="text-sm border border-slate-300 rounded-lg pl-8 pr-3 py-2 w-64 bg-white" />
        </div>
      </div>
      <p className="text-sm text-slate-500 mb-4">
        Every fund currently held across the model ranges. Click a fund for share classes, fees, links and the communications log.
      </p>

      <div className="space-y-2 mb-4">
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs text-slate-400 w-14">Range</span>
          {["All", "Core", "Passive", "ESG", "Income"].map((r) => (
            <button key={r} onClick={() => setRange(r)}
              className={`text-xs px-3 py-1.5 rounded-full border ${range === r ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-300 hover:border-slate-500"}`}>
              {r}{r !== "All" ? ` (${rangeCount(r)})` : ""}
            </button>
          ))}
          <span className="h-5 w-px bg-slate-200 mx-1" />
          <select value={asset} onChange={(e) => setAsset(e.target.value)} className="text-xs border border-slate-300 rounded-lg px-2 py-1.5 bg-white">
            <option value="All">All asset classes</option>
            {["Equities", "Fixed Interest", "Diversifiers"].map((a) => <option key={a}>{a}</option>)}
          </select>
          <select value={mgmt} onChange={(e) => setMgmt(e.target.value)} className="text-xs border border-slate-300 rounded-lg px-2 py-1.5 bg-white">
            <option value="All">Active + Passive</option>
            <option>Active</option>
            <option>Passive</option>
          </select>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs text-slate-400 w-14">Region</span>
          {["All", ...REGIONS].map((r) => {
            const n = r === "All" ? funds.length : funds.filter((f) => f.region === r).length;
            return (
              <button key={r} onClick={() => setRegion(r)}
                className={`text-xs px-3 py-1.5 rounded-full border ${region === r ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-300 hover:border-slate-500"}`}>
                {r}{r !== "All" ? ` (${n})` : ""}
              </button>
            );
          })}
        </div>
      </div>

      {list.length === 0 ? (
        <p className="text-slate-400 text-sm bg-white border border-dashed border-slate-300 rounded-xl p-8 text-center">No funds match.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {list.map((f) => (
            <div key={f.name} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 cursor-pointer" onClick={() => onOpen(f)}>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate flex items-center gap-2 flex-wrap">
                  {f.name}
                  <Badge cls={REGION_COLOURS[f.region]}>{f.region}</Badge>
                  <Badge cls={ASSET_COLOURS[f.assetClass]}>{f.assetClass}</Badge>
                  <Badge cls={MGMT_COLOURS[f.mgmt]}>{f.mgmt}</Badge>
                </div>
                <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5 flex-wrap">
                  <span>{f.house}</span>
                  <span>·</span>
                  <span>{f.shareClasses.length} share class{f.shareClasses.length === 1 ? "" : "es"}</span>
                  {f.shareClasses[0]?.ocf !== null && f.shareClasses[0]?.ocf !== undefined && (
                    <><span>·</span><span>OCF {pct(Math.min(...f.shareClasses.filter((c) => c.ocf !== null).map((c) => c.ocf)))}</span></>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {f.ranges.map((r) => <Badge key={r} cls={RANGE_COLOURS[r]}>{r}</Badge>)}
              </div>
              <div className="text-xs text-slate-400 hidden sm:flex items-center gap-1 w-10 justify-end shrink-0">
                <MessageSquare size={13} /> {commCounts[f.name] || 0}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MeetingsTab({ funds, onOpen }) {
  const [typeFilter, setTypeFilter] = useState("All");
  const all = useMemo(() => {
    const rows = [];
    for (const f of funds) {
      for (const c of loadComms(f.name)) rows.push({ ...c, fund: f });
    }
    return rows.sort((a, b) => b.date.localeCompare(a.date));
  }, [funds]);

  const list = all.filter((c) => typeFilter === "All" || c.type === typeFilter);

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Manager communications ({list.length})</h2>
      <p className="text-sm text-slate-500 mb-4">
        Everything logged across all funds, newest first. Log new entries from a fund's page.
      </p>
      <div className="flex gap-2 flex-wrap mb-4">
        {["All", ...COMM_TYPES].map((t) => {
          const n = t === "All" ? all.length : all.filter((c) => c.type === t).length;
          return (
            <button key={t} onClick={() => setTypeFilter(t)}
              className={`text-xs px-3 py-1.5 rounded-full border ${typeFilter === t ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-300 hover:border-slate-500"}`}>
              {t}{t !== "All" ? ` (${n})` : ""}
            </button>
          );
        })}
      </div>
      {list.length === 0 ? (
        <p className="text-slate-400 text-sm bg-white border border-dashed border-slate-300 rounded-xl p-8 text-center">
          Nothing logged yet. Open a fund and click "Log communication" to record a manager meeting, call or email.
        </p>
      ) : (
        <div className="space-y-3">
          {list.map((c) => (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge cls={COMM_COLOURS[c.type]}>{c.type}</Badge>
                <button onClick={() => onOpen(c.fund)} className="font-medium hover:underline">{c.fund.name}</button>
                <span className="text-xs text-slate-500">{c.date}{c.by ? ` · ${c.by}` : ""}{c.attendees ? ` · with ${c.attendees}` : ""}</span>
              </div>
              <p className="text-sm text-slate-700 mt-2 whitespace-pre-wrap">{c.summary}</p>
              {c.actions && (
                <p className="text-sm mt-1"><span className="font-medium text-slate-700">Actions:</span> <span className="text-slate-600">{c.actions}</span></p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FundPage({ fund, by, onBack }) {
  const [comms, setComms] = useState(() => loadComms(fund.name));
  const [form, setForm] = useState(null);

  const persist = (next) => {
    setComms(next);
    save(commsKey(fund.name), next);
  };

  const bestOcf = fund.shareClasses.filter((c) => c.ocf !== null && c.ocf !== undefined);

  return (
    <div className="space-y-6">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ChevronLeft size={16} /> Back to funds
      </button>

      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold flex items-center gap-2 flex-wrap">
              {fund.name}
              <Badge cls={REGION_COLOURS[fund.region]}>{fund.region}</Badge>
              <Badge cls={ASSET_COLOURS[fund.assetClass]}>{fund.assetClass}</Badge>
              <Badge cls={MGMT_COLOURS[fund.mgmt]}>{fund.mgmt}</Badge>
            </h2>
            <div className="text-sm text-slate-500 mt-1 flex items-center gap-2 flex-wrap">
              <span>{fund.house}</span>
              <span>·</span>
              <span className="flex items-center gap-1.5">Held in: {fund.ranges.map((r) => <Badge key={r} cls={RANGE_COLOURS[r]}>{r}</Badge>)}</span>
              {fund.yield !== null && fund.yield !== undefined && (
                <><span>·</span><span>Yield {pct(fund.yield)}{fund.yieldDate ? ` (as at ${fund.yieldDate})` : ""}</span></>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {fund.website && (
              <a href={fund.website} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm bg-slate-900 text-white px-3 py-2 rounded-lg hover:bg-slate-700">
                <Globe size={14} /> {fund.house} website <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="font-semibold mb-3">Share classes ({fund.shareClasses.length})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-400 text-left border-b border-slate-100">
                <th className="py-1.5 pr-3 font-medium">Class</th>
                <th className="py-1.5 pr-3 font-medium">ISIN</th>
                <th className="py-1.5 pr-3 font-medium">OCF</th>
                <th className="py-1.5 pr-3 font-medium">AMC</th>
                <th className="py-1.5 pr-3 font-medium">Platforms</th>
                <th className="py-1.5 font-medium">Factsheet</th>
              </tr>
            </thead>
            <tbody>
              {fund.shareClasses.map((c) => (
                <tr key={c.isin} className="border-b border-slate-50">
                  <td className="py-2 pr-3">{c.label || "-"}</td>
                  <td className="py-2 pr-3 font-mono text-xs">{c.isin}</td>
                  <td className="py-2 pr-3">{pct(c.ocf) || "-"}{c.ocfDate ? <span className="text-xs text-slate-400"> ({c.ocfDate})</span> : ""}</td>
                  <td className="py-2 pr-3">{pct(c.amc) || "-"}</td>
                  <td className="py-2 pr-3">
                    <span className="flex gap-1 flex-wrap">
                      {(c.platforms || []).length ? c.platforms.map((p) => <Badge key={p}>{p}</Badge>) : <span className="text-slate-300">-</span>}
                    </span>
                  </td>
                  <td className="py-2">
                    <a href={ftLink(c.isin)} target="_blank" rel="noopener noreferrer"
                      className="text-blue-600 hover:underline inline-flex items-center gap-1 text-xs">
                      <FileText size={12} /> FT tearsheet <ExternalLink size={10} />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {bestOcf.length === 0 && <p className="text-xs text-slate-400 mt-2">No fee data recorded in the master list for this fund.</p>}
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="font-semibold mb-3">Manager contact</h3>
          {fund.contactPhone || fund.contactEmail ? (
            <div className="space-y-2 text-sm">
              {fund.contactPhone && (
                <div className="flex items-center gap-2 text-slate-600"><Phone size={14} className="text-slate-400" /> {fund.contactPhone}</div>
              )}
              {fund.contactEmail && (
                <a href={`mailto:${fund.contactEmail}`} className="flex items-center gap-2 text-blue-600 hover:underline">
                  <Mail size={14} /> {fund.contactEmail}
                </a>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No contact recorded in the master list yet. Log one via a communication below and we can add it to the register.</p>
          )}
          {fund.notes && <p className="text-xs text-slate-500 mt-3 border-t border-slate-100 pt-2">{fund.notes}</p>}
        </div>

        <div className="md:col-span-2 bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-semibold flex items-center gap-2"><MessageSquare size={16} className="text-slate-400" /> Communications ({comms.length})</h3>
            <button onClick={() => setForm({ type: "Meeting", date: today(), attendees: "", summary: "", actions: "" })}
              className="flex items-center gap-1 bg-slate-900 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-slate-700">
              <Plus size={14} /> Log communication
            </button>
          </div>
          <p className="text-xs text-slate-400 mb-4">Emails, calls and meetings with {fund.house}. Stored locally in this browser for now.</p>
          {comms.length === 0 ? (
            <p className="text-sm text-slate-400">Nothing logged yet.</p>
          ) : (
            <div className="space-y-2">
              {[...comms].sort((a, b) => b.date.localeCompare(a.date)).map((c) => (
                <div key={c.id} className="border border-slate-200 rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="flex items-center gap-2 text-sm">
                      <Badge cls={COMM_COLOURS[c.type]}>{c.type}</Badge>
                      <span className="text-slate-500 text-xs">{c.date}{c.by ? ` · ${c.by}` : ""}{c.attendees ? ` · with ${c.attendees}` : ""}</span>
                    </span>
                    <ConfirmDelete onConfirm={() => persist(comms.filter((x) => x.id !== c.id))} />
                  </div>
                  <p className="text-sm text-slate-700 mt-1 whitespace-pre-wrap">{c.summary}</p>
                  {c.actions && (
                    <p className="text-sm mt-1"><span className="font-medium text-slate-700">Actions:</span> <span className="text-slate-600">{c.actions}</span></p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={() => setForm(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">Log communication · {fund.name}</h3>
              <button onClick={() => setForm(null)} className="text-slate-400 hover:text-slate-700"><X size={18} /></button>
            </div>
            <div className="space-y-3">
              <div className="flex gap-3">
                <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}
                  className="flex-1 text-sm border border-slate-300 rounded-lg px-3 py-2 bg-white">
                  {COMM_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
                <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })}
                  className="flex-1 text-sm border border-slate-300 rounded-lg px-3 py-2" />
              </div>
              <input value={form.attendees} onChange={(e) => setForm({ ...form, attendees: e.target.value })}
                placeholder="Attendees / manager contacts (e.g. J Smith - PM, our side: HE)"
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2" />
              <textarea value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} rows={5}
                placeholder="Notes: what was discussed, positioning, performance drivers, team changes... (no client personal data)"
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2" />
              <input value={form.actions} onChange={(e) => setForm({ ...form, actions: e.target.value })}
                placeholder="Action points / follow-ups (optional)"
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2" />
              <button
                onClick={() => {
                  if (!form.summary.trim()) return;
                  persist([{ id: uid(), type: form.type, date: form.date, attendees: form.attendees.trim(),
                    summary: form.summary.trim(), actions: form.actions.trim(), by }, ...comms]);
                  setForm(null);
                }}
                disabled={!form.summary.trim()}
                className="w-full bg-slate-900 text-white text-sm py-2.5 rounded-lg hover:bg-slate-700 disabled:opacity-40">
                Save communication
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
