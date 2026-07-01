"use client";

import { FormEvent, useEffect, useState } from "react";
import clsx from "clsx";
import { Activity, Check, ClipboardCheck, Clock3, Cpu, Download, Edit3, Layers3, LoaderCircle, Play, Plus, ServerCog, Trash2, X } from "lucide-react";
import { deleteScenario, getAttackReport, getLabVpn, getStudentDashboard, listLabSessions, saveScenario, startLab, stopLab, updateScenario, type ApiLab, type ApiMachine, type ApiScenario, type AttackReport, type StudentDashboard } from "@/lib/api";

function Panel({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return <section className="rounded-lg border border-ink/10 bg-white shadow-sm"><div className="border-b border-ink/10 p-4"><p className="text-xs font-bold uppercase text-ink/44">{eyebrow}</p><h2 className="mt-1 text-xl font-black text-ink">{title}</h2></div>{children}</section>;
}

function Action({ children, icon: Icon, onClick, disabled, spinning }: { children: React.ReactNode; icon: typeof Play; onClick?: () => void; disabled?: boolean; spinning?: boolean }) {
  return <button type="button" onClick={onClick} disabled={disabled} className={clsx("inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-3 text-sm font-bold", disabled ? "cursor-not-allowed bg-ink/8 text-ink/35" : "bg-canopy text-white hover:bg-fern")}><Icon size={16} className={spinning ? "animate-spin" : undefined} />{children}</button>;
}

function formatAttackReport(report: AttackReport) {
  const lines = [report.summary, "", "Attack chain"];
  report.attack_chain.forEach((phase, index) => {
    lines.push((index + 1) + ". " + phase.tactic + " - " + phase.technique_id + " - " + phase.technique + " (" + phase.event_count + " events)");
  });
  return lines.join("\n");
}

function LabRows({ labs, machines, busyLab, onDownload, onReport, onStart, onStop }: { labs: ApiLab[]; machines: ApiMachine[]; busyLab: string | null; onDownload: (lab: ApiLab) => void; onReport: (lab: ApiLab) => void; onStart: (lab: ApiLab) => void; onStop: (lab: ApiLab) => void }) {
  return <div className="divide-y divide-ink/10">{labs.map((lab) => {
    const locked = lab.status === "locked";
    const running = lab.status === "running";
    const machineNames = lab.machine_ids.map((id) => machines.find((machine) => machine.id === id)?.name).filter(Boolean).join(", ");
    return <article key={lab.id} className="p-4"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h3 className="text-base font-black text-ink">{lab.name}</h3><span className={clsx("rounded-full px-2.5 py-1 text-xs font-bold", locked ? "bg-ink/8 text-ink/45" : running ? "bg-mint/25 text-fern" : "bg-sun/20 text-ink/70")}>{locked ? "Locked" : running ? "Running" : "Ready"}</span></div><p className="mt-1 text-sm leading-6 text-ink/58">{lab.description}</p><p className="mt-2 text-xs font-semibold text-ink/48">{lab.level} - {lab.runtime} - {machineNames}</p></div><div className="flex flex-wrap gap-2">{running ? <><Action icon={busyLab === lab.id ? LoaderCircle : Download} spinning={busyLab === lab.id} onClick={() => onDownload(lab)} disabled={busyLab === lab.id}>{busyLab === lab.id ? "Preparing" : "Download VPN"}</Action><Action icon={busyLab === lab.id ? LoaderCircle : ClipboardCheck} spinning={busyLab === lab.id} onClick={() => onReport(lab)} disabled={busyLab === lab.id}>{busyLab === lab.id ? "Loading" : "Report"}</Action><button type="button" onClick={() => onStop(lab)} disabled={busyLab === lab.id} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-clay/25 px-3 text-sm font-bold text-clay hover:bg-clay/10 disabled:cursor-not-allowed disabled:opacity-50">{busyLab === lab.id ? <LoaderCircle size={16} className="animate-spin" /> : <X size={16} />}Stop</button></> : <Action icon={busyLab === lab.id ? LoaderCircle : Play} spinning={busyLab === lab.id} onClick={() => onStart(lab)} disabled={locked || busyLab === lab.id}>{locked ? "Locked" : busyLab === lab.id ? "Starting" : "Start"}</Action>}</div></div>{lab.tasks.length ? <div className="mt-4 rounded-md border border-ink/10 bg-cloud/60 p-3"><p className="text-xs font-bold uppercase text-ink/45">Flags and questions</p><ul className="mt-2 grid gap-2 text-sm text-ink/68">{lab.tasks.map((task) => <li key={task} className="flex gap-2"><span className="mt-1 grid h-4 w-4 shrink-0 place-items-center rounded-full border border-fern/35 text-transparent">.</span><span>{task}</span></li>)}</ul></div> : null}<p className="mt-3 text-xs text-ink/52"><span className="font-bold text-fern">Next:</span> {lab.next_step}</p></article>;
  })}</div>;
}

function Builder({
  apiUrl,
  machines,
  scenarios,
  onSaved,
  onUpdated,
  onDeleted,
}: {
  apiUrl: string;
  machines: ApiMachine[];
  scenarios: ApiScenario[];
  onSaved: (scenario: ApiScenario) => void;
  onUpdated: (scenario: ApiScenario) => void;
  onDeleted: (scenarioId: string, message: string) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selected.length && machines.length) setSelected([machines[0].id]);
  }, [machines, selected.length]);

  function toggle(id: string) { setSelected((items) => items.includes(id) ? items.filter((item) => item !== id) : [...items, id]); }

  function resetForm() {
    setEditingId(null);
    setName("");
    setSelected(machines.length ? [machines[0].id] : []);
    setError("");
  }

  function edit(scenario: ApiScenario) {
    setEditingId(scenario.id);
    setName(scenario.name);
    setSelected(scenario.machine_ids);
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || !selected.length) {
      setError(!name.trim() ? "Enter a scenario name." : "Select at least one approved machine.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editingId) {
        onUpdated(await updateScenario(apiUrl, editingId, name.trim(), selected));
      } else {
        onSaved(await saveScenario(apiUrl, name.trim(), selected));
      }
      resetForm();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save the scenario.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(scenario: ApiScenario) {
    if (!window.confirm("Remove " + scenario.name + "?")) return;
    try {
      const result = await deleteScenario(apiUrl, scenario.id);
      onDeleted(scenario.id, result.message);
      if (editingId === scenario.id) resetForm();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to remove the scenario.");
    }
  }

  return <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]"><Panel eyebrow="Scenario builder" title={editingId ? "Edit personal lab" : "Create a personal lab"}><form onSubmit={submit} className="p-4"><label className="block text-sm font-bold text-ink/72">Scenario name<input value={name} onChange={(event) => setName(event.target.value)} className="mt-2 block min-h-11 w-full rounded-md border border-ink/15 px-3 outline-none focus:border-fern" placeholder="e.g. Web request investigation" /></label><p className="mt-5 text-sm font-black text-ink">Approved machine layout</p><p className="mt-1 text-xs leading-5 text-ink/54">Personal scenarios are saved only to your student workspace.</p><div className="mt-4 grid gap-3 sm:grid-cols-2">{machines.map((machine) => { const checked = selected.includes(machine.id); return <button key={machine.id} type="button" onClick={() => toggle(machine.id)} className={clsx("rounded-md border p-3 text-left transition", checked ? "border-fern bg-mint/10" : "border-ink/10 hover:border-fern/50")}><span className="flex items-center justify-between"><Cpu size={18} className="text-canopy" /><span className={clsx("grid h-5 w-5 place-items-center rounded-full", checked ? "bg-fern text-white" : "bg-ink/10 text-transparent")}><Check size={13} /></span></span><p className="mt-3 text-sm font-black text-ink">{machine.name}</p><p className="mt-1 text-xs text-ink/50">{machine.os_type}</p></button>; })}</div>{error ? <p className="mt-4 rounded-md bg-clay/10 px-3 py-2 text-sm font-semibold text-clay">{error}</p> : null}<div className="mt-5 flex flex-wrap justify-end gap-2">{editingId ? <button type="button" onClick={resetForm} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-sm font-bold text-ink/65 hover:border-fern/50"><X size={16} />Cancel</button> : null}<Action icon={editingId ? Edit3 : Plus} disabled={saving}>{saving ? "Saving" : editingId ? "Update scenario" : "Save scenario"}</Action></div></form></Panel><Panel eyebrow="Saved scenarios" title="Your workspace library"><div className="divide-y divide-ink/10">{scenarios.length ? scenarios.map((scenario) => <div key={scenario.id} className="p-4"><div className="flex justify-between gap-3"><div><p className="text-sm font-black text-ink">{scenario.name}</p><p className="mt-1 text-xs text-ink/54">{scenario.machine_ids.length} approved machines</p></div><span className="rounded-full bg-mint/20 px-2.5 py-1 text-xs font-bold text-fern">Saved</span></div><p className="mt-3 text-xs font-semibold text-ink/45">Updated {scenario.updated_at}</p><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => edit(scenario)} className="inline-flex min-h-9 items-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50"><Edit3 size={15} />Edit</button><button type="button" onClick={() => remove(scenario)} className="inline-flex min-h-9 items-center gap-2 rounded-md border border-clay/25 px-3 text-xs font-bold text-clay hover:bg-clay/10"><Trash2 size={15} />Remove</button></div></div>) : <p className="p-6 text-center text-sm text-ink/54">No personal scenarios yet.</p>}</div></Panel></div>;
}

export default function StudentPortal({ apiUrl, view }: { apiUrl: string; view: string }) {
  const [data, setData] = useState<StudentDashboard | null>(null); const [error, setError] = useState(""); const [busyLab, setBusyLab] = useState<string | null>(null); const [notice, setNotice] = useState(""); const [reportLog, setReportLog] = useState(""); const [scenarios, setScenarios] = useState<ApiScenario[]>([]);
  useEffect(() => { let active = true; getStudentDashboard(apiUrl).then((dashboard) => { if (active) { setData(dashboard); setScenarios(dashboard.scenarios); } }).catch((reason) => active && setError(reason instanceof Error ? reason.message : "Unable to load your workspace.")); return () => { active = false; }; }, [apiUrl]);
  function downloadConfig(filename: string, config: string) {
    const url = URL.createObjectURL(new Blob([config], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
  function setLabStatus(labId: string, status: ApiLab["status"], nextStep: string) {
    setData((current) => current ? { ...current, assignments: current.assignments.map((lab) => lab.id === labId ? { ...lab, status, next_step: nextStep } : lab) } : current);
  }
  async function start(lab: ApiLab) { setBusyLab(lab.id); setNotice(""); try { const result = await startLab(apiUrl, lab.id); setLabStatus(lab.id, "running", "Download the VPN config and connect with WireGuard"); setNotice(result.message); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Unable to start the lab."); } finally { setBusyLab(null); } }
  async function download(lab: ApiLab) { setBusyLab(lab.id); setNotice(""); try { const result = await getLabVpn(apiUrl, lab.id); downloadConfig(result.wireguard_filename, result.wireguard_config); setLabStatus(lab.id, "running", "Download the VPN config and connect with WireGuard"); setNotice("Downloaded " + result.wireguard_filename + "."); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Unable to download the VPN config."); } finally { setBusyLab(null); } }
  async function report(lab: ApiLab) { setBusyLab(lab.id); setNotice(""); try { const sessions = await listLabSessions(apiUrl, lab.id); const latest = [...sessions].sort((left, right) => Date.parse(right.started_at) - Date.parse(left.started_at))[0]; if (!latest) { setNotice("No sessions are available for " + lab.name + "."); return; } const result = await getAttackReport(apiUrl, latest.id); setReportLog(formatAttackReport(result)); setNotice("Loaded telemetry report for " + lab.name + "."); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Unable to load telemetry report."); } finally { setBusyLab(null); } }
  async function stop(lab: ApiLab) { setBusyLab(lab.id); setNotice(""); try { await stopLab(apiUrl, lab.id); setLabStatus(lab.id, "ready", "Start the lab when you are ready"); setNotice(lab.name + " has been stopped."); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Unable to stop the lab."); } finally { setBusyLab(null); } }
  if (error) return <p className="rounded-lg border border-clay/25 bg-clay/10 p-4 text-sm font-semibold text-clay">{error}</p>;
  if (!data) return <p className="rounded-lg border border-ink/10 bg-white p-8 text-center text-sm font-semibold text-ink/58">Loading your learning workspace...</p>;
  const reportPanel = reportLog ? <Panel eyebrow="Telemetry report" title="Attack chain reconstruction"><pre className="max-h-72 overflow-auto whitespace-pre-wrap bg-ink p-4 text-xs leading-5 text-white">{reportLog}</pre></Panel> : null;
  const labs = <Panel eyebrow="Assigned labs" title="Continue learning"><LabRows labs={data.assignments} machines={data.machines} busyLab={busyLab} onDownload={download} onReport={report} onStart={start} onStop={stop} /></Panel>;
  const builder = <Builder apiUrl={apiUrl} machines={data.machines} scenarios={scenarios} onSaved={(scenario) => { setScenarios((items) => [scenario, ...items]); setNotice(scenario.name + " has been saved to your workspace."); }} onUpdated={(scenario) => { setScenarios((items) => items.map((item) => item.id === scenario.id ? scenario : item)); setNotice(scenario.name + " has been updated."); }} onDeleted={(scenarioId, message) => { setScenarios((items) => items.filter((item) => item.id !== scenarioId)); setNotice(message); }} />;
  const library = <Panel eyebrow="Machine library" title="Approved environments"><div className="grid divide-y divide-ink/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0">{data.machines.map((machine) => <div key={machine.id} className="p-4"><div className="flex items-center justify-between"><span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy"><ServerCog size={19} /></span><span className="rounded-md bg-cloud px-2 py-1 text-xs font-bold text-ink/55">{machine.os_type}</span></div><p className="mt-4 text-sm font-black text-ink">{machine.name}</p><p className="mt-1 text-xs leading-5 text-ink/54">{machine.description}</p><p className="mt-3 truncate text-xs font-semibold text-fern">{machine.imageUrl}</p></div>)}</div></Panel>;
  if (view === "Assigned labs") return <div className="space-y-4">{notice ? <p className="rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">{notice}</p> : null}{reportPanel}{labs}</div>;
  if (view === "My scenarios") return <div className="space-y-4">{notice ? <p className="rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">{notice}</p> : null}{builder}</div>;
  if (view === "Machine library") return library;
  return <div className="space-y-6">{notice ? <p className="rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">{notice}</p> : null}<div className="grid gap-4 md:grid-cols-2">{[["Assigned labs", String(data.assignments.length), "VPN configs available", Download], ["Personal scenarios", String(scenarios.length), "saved workspaces", Layers3]].map(([label, value, detail, Icon]) => { const Metric = Icon as typeof Activity; return <div key={label as string} className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm"><div className="flex justify-between"><div><p className="text-sm font-semibold text-ink/55">{label as string}</p><p className="mt-2 text-3xl font-black text-ink">{value as string}</p></div><span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy"><Metric size={20} /></span></div><p className="mt-3 text-xs font-bold text-fern">{detail as string}</p></div>; })}</div><div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">{labs}<Panel eyebrow="Recent activity" title="Lab updates"><div className="divide-y divide-ink/10">{data.activity.map((item) => <div key={item.id} className="flex gap-3 p-4"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-cloud text-fern"><Clock3 size={16} /></span><div><p className="text-sm font-black text-ink">{item.title}</p><p className="mt-1 text-xs text-ink/54">{item.detail}</p><p className="mt-2 text-xs font-semibold text-ink/42">{item.when}</p></div></div>)}</div></Panel></div>{builder}</div>;
}
