"use client";

import { FormEvent, useEffect, useState } from "react";
import clsx from "clsx";
import {
  Activity,
  ArrowLeft,
  Check,
  ClipboardCheck,
  Clock3,
  Cpu,
  Download,
  Edit3,
  FileText,
  Layers3,
  LoaderCircle,
  Play,
  Plus,
  Save,
  ServerCog,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import {
  type ApiLab,
  type ApiMachine,
  type ApiScenario,
  type AttackReport,
  deleteScenario,
  downloadLabAttachment,
  getAttackReport,
  getLabAttachments,
  getLabVpn,
  getScenarioVpn,
  getStudentDashboard,
  type LabAttachment,
  listLabSessions,
  openAttackReport,
  type ReportType,
  saveLabAnswers,
  saveScenario,
  startLab,
  startScenario,
  stopLab,
  stopScenario,
  type StudentDashboard,
  submitLab,
  updateScenario,
} from "@/lib/api";

function Panel(
  { eyebrow, title, children }: {
    eyebrow: string;
    title: string;
    children: React.ReactNode;
  },
) {
  return (
    <section className="rounded-lg border border-ink/10 bg-white shadow-sm">
      <div className="border-b border-ink/10 p-4">
        <p className="text-xs font-bold uppercase text-ink/44">{eyebrow}</p>
        <h2 className="mt-1 text-xl font-black text-ink">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Action(
  { children, icon: Icon, onClick, disabled, spinning }: {
    children: React.ReactNode;
    icon: typeof Play;
    onClick?: () => void;
    disabled?: boolean;
    spinning?: boolean;
  },
) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-3 text-sm font-bold",
        disabled
          ? "cursor-not-allowed bg-ink/8 text-ink/35"
          : "bg-canopy text-white hover:bg-fern",
      )}
    >
      <Icon size={16} className={spinning ? "animate-spin" : undefined} />
      {children === "Save answers" ? "Submit lab" : children}
    </button>
  );
}

function formatAttackReport(report: AttackReport) {
  const lines = [report.summary, "", "Attack chain"];
  report.attack_chain.forEach((phase, index) => {
    lines.push(
      (index + 1) + ". " + phase.tactic + " - " + phase.technique_id + " - " +
        phase.technique + " (" + phase.event_count + " events)",
    );
  });
  return lines.join("\n");
}

function LabRows(
  { labs, machines, onOpen }: {
    labs: ApiLab[];
    machines: ApiMachine[];
    onOpen: (lab: ApiLab) => void;
  },
) {
  return (
    <div className="divide-y divide-ink/10">
      {labs.map((lab) => {
        const locked = lab.status === "locked";
        const running = lab.status === "running";
        const machineNames = lab.machine_ids.map((id) =>
          machines.find((machine) => machine.id === id)?.name
        ).filter(Boolean).join(", ");
        return (
          <button
            key={lab.id}
            type="button"
            onClick={() => onOpen(lab)}
            className="block w-full p-4 text-left transition hover:bg-cloud/60 focus:bg-cloud/60 focus:outline-none"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-black text-ink">{lab.name}</h3>
                  <span
                    className={clsx(
                      "rounded-full px-2.5 py-1 text-xs font-bold",
                      locked
                        ? "bg-ink/8 text-ink/45"
                        : running
                        ? "bg-mint/25 text-fern"
                        : "bg-sun/20 text-ink/70",
                    )}
                  >
                    {locked ? "Locked" : running ? "Running" : "Ready"}
                  </span>
                </div>
                <p className="mt-1 text-sm leading-6 text-ink/58">
                  {lab.description}
                </p>
                <p className="mt-2 text-xs font-semibold text-ink/48">
                  {lab.level} · {lab.runtime} · {machineNames}
                </p>
              </div>
              <span className="shrink-0 rounded-md border border-fern/25 px-3 py-2 text-sm font-bold text-fern">
                Open lab
              </span>
            </div>
            <p className="mt-3 text-xs text-ink/52">
              <span className="font-bold text-fern">Next:</span> {lab.next_step}
            </p>
          </button>
        );
      })}
    </div>
  );
}

function LabWorkspace({
  apiUrl,
  lab,
  machines,
  busy,
  reportLog,
  onClose,
  onStart,
  onStop,
  onDownloadVpn,
  onReport,
  onAnswersSaved,
  onSubmitted,
}: {
  apiUrl: string;
  lab: ApiLab;
  machines: ApiMachine[];
  busy: boolean;
  reportLog: string;
  onClose: () => void;
  onStart: (lab: ApiLab) => Promise<void>;
  onStop: (lab: ApiLab) => Promise<void>;
  onDownloadVpn: (lab: ApiLab) => Promise<void>;
  onReport: (lab: ApiLab, reportType: ReportType) => Promise<void>;
  onAnswersSaved: (labId: string, questions: ApiLab["questions"]) => void;
  onSubmitted: (labId: string, score: number, maxScore: number) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>(() =>
    Object.fromEntries(lab.questions.map((item) => [item.id, item.answer]))
  );
  const [attachments, setAttachments] = useState<LabAttachment[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const assignedMachines = lab.machine_ids.map((id) =>
    machines.find((machine) => machine.id === id)
  ).filter((machine): machine is ApiMachine => Boolean(machine));

  useEffect(() => {
    setAnswers(
      Object.fromEntries(lab.questions.map((item) => [item.id, item.answer])),
    );
  }, [lab.id, lab.questions]);
  useEffect(() => {
    getLabAttachments(apiUrl, lab.id).then((result) =>
      setAttachments(result.attachments)
    ).catch(() => setAttachments([]));
  }, [apiUrl, lab.id, lab.status]);

  async function saveAnswers() {
    if (
      !window.confirm(
        "Submit this lab for automatic grading and teacher review?",
      )
    ) return;
    setSaving(true);
    setMessage("");
    try {
      const result = await saveLabAnswers(apiUrl, lab.id, answers);
      onAnswersSaved(lab.id, result.questions);
      const submission = await submitLab(apiUrl, lab.id);
      onSubmitted(lab.id, submission.auto_score, submission.max_score);
      setMessage(
        submission.message + " Automatic score: " + submission.auto_score +
          "/" + submission.max_score + ".",
      );
    } catch (reason) {
      setMessage(
        reason instanceof Error ? reason.message : "Unable to submit the lab.",
      );
    } finally {
      setSaving(false);
    }
  }
  async function startWorkspace() {
    await onStart(lab);
    try {
      setAttachments((await getLabAttachments(apiUrl, lab.id)).attachments);
    } catch {}
  }
  async function getAttachment(item: LabAttachment) {
    try {
      const result = await downloadLabAttachment(apiUrl, item);
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "Unable to download attachment.",
      );
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-cloud">
      <header className="sticky top-0 z-10 border-b border-ink/10 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-10 items-center gap-2 text-sm font-bold text-ink/65 hover:text-fern"
          >
            <ArrowLeft size={18} />Back to labs
          </button>
          <div className="flex flex-wrap gap-2">
            <Action
              icon={ClipboardCheck}
              onClick={() => onReport(lab, "academic")}
              disabled={busy}
            >
              Academic report
            </Action>
            <Action
              icon={ClipboardCheck}
              onClick={() => onReport(lab, "professional")}
              disabled={busy}
            >
              Professional report
            </Action>
            {lab.status === "running"
              ? (
                <>
                  <Action
                    icon={Download}
                    onClick={() => onDownloadVpn(lab)}
                    disabled={busy}
                  >
                    VPN config
                  </Action>
                  <button
                    type="button"
                    onClick={() => onStop(lab)}
                    disabled={busy}
                    className="inline-flex min-h-10 items-center gap-2 rounded-md border border-clay/30 px-3 text-sm font-bold text-clay"
                  >
                    <X size={16} />Stop lab
                  </button>
                </>
              )
              : (
                <Action
                  icon={busy ? LoaderCircle : Play}
                  spinning={busy}
                  onClick={startWorkspace}
                  disabled={busy || lab.status === "locked"}
                >
                  {lab.status === "locked"
                    ? "Locked"
                    : busy
                    ? "Starting"
                    : "Start lab"}
                </Action>
              )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="rounded-xl bg-ink p-6 text-white shadow-lg sm:p-8">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase">
              {lab.level}
            </span>
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase">
              {lab.runtime}
            </span>
            <span
              className={clsx(
                "rounded-full px-3 py-1 text-xs font-bold uppercase",
                lab.status === "running" ? "bg-mint text-fern" : "bg-white/10",
              )}
            >
              {lab.status}
            </span>
          </div>
          <h1 className="mt-5 text-3xl font-black sm:text-4xl">{lab.name}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-white/70 sm:text-base">
            {lab.description}
          </p>
          <p className="mt-5 text-sm font-bold text-mint">{lab.next_step}</p>
        </div>
        {message
          ? (
            <p className="mt-4 rounded-lg border border-fern/25 bg-mint/20 px-4 py-3 text-sm font-bold text-fern">
              {message}
            </p>
          )
          : null}
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,.65fr)]">
          <div className="space-y-6">
            <Panel eyebrow="Lab questions" title="Record your findings">
              <div className="space-y-5 p-4 sm:p-6">
                {lab.questions.length
                  ? lab.questions.map((question, index) => (
                    <label key={question.id} className="block">
                      <span className="flex gap-3 text-sm font-black text-ink">
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-mint/30 text-xs text-fern">
                          {index + 1}
                        </span>
                        {question.prompt}
                      </span>
                      <textarea
                        value={answers[question.id] ?? ""}
                        onChange={(event) =>
                          setAnswers((items) => ({
                            ...items,
                            [question.id]: event.target.value,
                          }))}
                        className="mt-3 min-h-28 w-full resize-y rounded-lg border border-ink/15 p-3 text-sm leading-6 outline-none focus:border-fern"
                        placeholder="Enter your answer, evidence, or flag…"
                        maxLength={4000}
                      />
                    </label>
                  ))
                  : (
                    <p className="text-sm text-ink/50">
                      This lab has no questions yet.
                    </p>
                  )} {lab.questions.length
                  ? (
                    <div className="flex justify-end">
                      <Action
                        icon={saving ? LoaderCircle : Save}
                        spinning={saving}
                        onClick={saveAnswers}
                        disabled={saving}
                      >
                        {saving ? "Saving" : "Save answers"}
                      </Action>
                    </div>
                  )
                  : null}
              </div>
            </Panel>
            {reportLog
              ? (
                <Panel
                  eyebrow="Telemetry report"
                  title="Attack chain reconstruction"
                >
                  <pre className="max-h-96 overflow-auto whitespace-pre-wrap bg-ink p-4 text-xs leading-5 text-white">{reportLog}</pre>
                </Panel>
              )
              : null}
            <Panel eyebrow="Machine layout" title="Targets in this lab">
              <div className="grid gap-px bg-ink/10 sm:grid-cols-2">
                {assignedMachines.map((machine) => (
                  <div key={machine.id} className="bg-white p-5">
                    <div className="flex items-center justify-between">
                      <span className="grid h-10 w-10 place-items-center rounded-lg bg-mint/20 text-fern">
                        <ServerCog size={19} />
                      </span>
                      <span className="rounded bg-cloud px-2 py-1 text-xs font-bold text-ink/50">
                        {machine.os_type}
                      </span>
                    </div>
                    <h3 className="mt-4 font-black text-ink">{machine.name}</h3>
                    <p className="mt-2 text-sm leading-6 text-ink/55">
                      {machine.description}
                    </p>
                    <p className="mt-3 truncate text-xs font-semibold text-fern">
                      {machine.imageUrl}
                    </p>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
          <aside className="space-y-6">
            <Panel eyebrow="Connection" title="Lab access">
              <div className="p-4">
                <div
                  className={clsx(
                    "rounded-lg p-4",
                    lab.status === "running" ? "bg-mint/20" : "bg-cloud",
                  )}
                >
                  <ShieldCheck
                    className={lab.status === "running"
                      ? "text-fern"
                      : "text-ink/35"}
                  />
                  <p className="mt-3 text-sm font-black text-ink">
                    {lab.status === "running"
                      ? "Environment running"
                      : "Environment offline"}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-ink/55">
                    {lab.status === "running"
                      ? "Download the WireGuard configuration and connect to the isolated lab network."
                      : "The environment is offline; reports and attachments remain available."}
                  </p>
                  {lab.status === "running" && lab.lab_cidr
                    ? (
                      <div className="mt-4 border-t border-fern/15 pt-3">
                        <p className="text-[11px] font-black uppercase tracking-wide text-fern">
                          Lab network
                        </p>
                        <code className="mt-2 inline-block rounded bg-white px-2 py-1 text-sm font-bold text-canopy">{lab.lab_cidr}</code>
                      </div>
                    )
                    : null}
                </div>
                {lab.status === "running"
                  ? (
                    <button
                      type="button"
                      onClick={() => onDownloadVpn(lab)}
                      className="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md bg-canopy px-3 text-sm font-bold text-white"
                    >
                      <Download size={16} />Download VPN config
                    </button>
                  )
                  : null}
              </div>
            </Panel>
            <Panel eyebrow="Resources" title="Attachments">
              <div className="divide-y divide-ink/10">
                {attachments.length
                  ? attachments.map((item) => (
                    <button
                      type="button"
                      key={item.machine_id + item.download_url}
                      onClick={() => getAttachment(item)}
                      className="flex w-full items-center gap-3 p-4 text-left hover:bg-cloud"
                    >
                      <span className="grid h-9 w-9 place-items-center rounded bg-cloud text-fern">
                        <FileText size={17} />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-black text-ink">
                          {item.filename}
                        </span>
                        <span className="block truncate text-xs text-ink/45">
                          {item.machine_name}
                        </span>
                      </span>
                      <Download
                        size={16}
                        className="ml-auto shrink-0 text-fern"
                      />
                    </button>
                  ))
                  : (
                    <p className="p-4 text-sm text-ink/50">
                      No attachments for this lab.
                    </p>
                  )}
              </div>
            </Panel>
          </aside>
        </div>
      </main>
    </div>
  );
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
  const [busyScenario, setBusyScenario] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selected.length && machines.length) setSelected([machines[0].id]);
  }, [machines, selected.length]);

  function toggle(id: string) {
    setSelected((items) =>
      items.includes(id) ? items.filter((item) => item !== id) : [...items, id]
    );
  }

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
      setError(
        !name.trim()
          ? "Enter a scenario name."
          : "Select at least one approved machine.",
      );
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editingId) {
        onUpdated(
          await updateScenario(apiUrl, editingId, name.trim(), selected),
        );
      } else {
        onSaved(await saveScenario(apiUrl, name.trim(), selected));
      }
      resetForm();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to save the scenario.",
      );
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
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to remove the scenario.",
      );
    }
  }

  function downloadConfig(filename: string, config: string) {
    const url = URL.createObjectURL(new Blob([config], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function start(scenario: ApiScenario) {
    setBusyScenario(scenario.id);
    setError("");
    try {
      const result = await startScenario(apiUrl, scenario.id);
      downloadConfig(result.wireguard_filename, result.wireguard_config);
      onUpdated({
        ...scenario,
        status: "running",
        running_session_id: result.id,
      });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to start the scenario.",
      );
    } finally {
      setBusyScenario(null);
    }
  }

  async function downloadVpn(scenario: ApiScenario) {
    setBusyScenario(scenario.id);
    setError("");
    try {
      const result = await getScenarioVpn(apiUrl, scenario.id);
      downloadConfig(result.wireguard_filename, result.wireguard_config);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to download the VPN config.",
      );
    } finally {
      setBusyScenario(null);
    }
  }

  async function stop(scenario: ApiScenario) {
    setBusyScenario(scenario.id);
    setError("");
    try {
      await stopScenario(apiUrl, scenario.id);
      onUpdated({ ...scenario, status: "saved", running_session_id: null });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to stop the scenario.",
      );
    } finally {
      setBusyScenario(null);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
      <Panel
        eyebrow="Scenario builder"
        title={editingId ? "Edit personal lab" : "Create a personal lab"}
      >
        <form onSubmit={submit} className="p-4">
          <label className="block text-sm font-bold text-ink/72">
            Scenario name<input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-2 block min-h-11 w-full rounded-md border border-ink/15 px-3 outline-none focus:border-fern"
              placeholder="e.g. Web request investigation"
            />
          </label>
          <p className="mt-5 text-sm font-black text-ink">
            Approved machine layout
          </p>
          <p className="mt-1 text-xs leading-5 text-ink/54">
            Personal scenarios run in your own isolated workspace.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {machines.map((machine) => {
              const checked = selected.includes(machine.id);
              return (
                <button
                  key={machine.id}
                  type="button"
                  onClick={() => toggle(machine.id)}
                  className={clsx(
                    "rounded-md border p-3 text-left transition",
                    checked
                      ? "border-fern bg-mint/10"
                      : "border-ink/10 hover:border-fern/50",
                  )}
                >
                  <span className="flex items-center justify-between">
                    <Cpu size={18} className="text-canopy" />
                    <span
                      className={clsx(
                        "grid h-5 w-5 place-items-center rounded-full",
                        checked
                          ? "bg-fern text-white"
                          : "bg-ink/10 text-transparent",
                      )}
                    >
                      <Check size={13} />
                    </span>
                  </span>
                  <p className="mt-3 text-sm font-black text-ink">
                    {machine.name}
                  </p>
                  <p className="mt-1 text-xs text-ink/50">{machine.os_type}</p>
                </button>
              );
            })}
          </div>
          {error
            ? (
              <p className="mt-4 rounded-md bg-clay/10 px-3 py-2 text-sm font-semibold text-clay">
                {error}
              </p>
            )
            : null}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            {editingId
              ? (
                <button
                  type="button"
                  onClick={resetForm}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-sm font-bold text-ink/65 hover:border-fern/50"
                >
                  <X size={16} />Cancel
                </button>
              )
              : null}
            <Action icon={editingId ? Edit3 : Plus} disabled={saving}>
              {saving
                ? "Saving"
                : editingId
                ? "Update scenario"
                : "Save scenario"}
            </Action>
          </div>
        </form>
      </Panel>
      <Panel eyebrow="Saved scenarios" title="Your workspace library">
        <div className="divide-y divide-ink/10">
          {scenarios.length
            ? scenarios.map((scenario) => {
              const busy = busyScenario === scenario.id;
              const running = scenario.status === "running";
              return (
                <div key={scenario.id} className="p-4">
                  <div className="flex justify-between gap-3">
                    <div>
                      <p className="text-sm font-black text-ink">
                        {scenario.name}
                      </p>
                      <p className="mt-1 text-xs text-ink/54">
                        {scenario.machine_ids.length} approved machines
                      </p>
                    </div>
                    <span
                      className={clsx(
                        "rounded-full px-2.5 py-1 text-xs font-bold",
                        running
                          ? "bg-mint/30 text-fern"
                          : "bg-cloud text-ink/55",
                      )}
                    >
                      {running ? "Running" : "Saved"}
                    </span>
                  </div>
                  <p className="mt-3 text-xs font-semibold text-ink/45">
                    Updated {scenario.updated_at}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {running
                      ? (
                        <>
                          <Action
                            icon={Download}
                            onClick={() => downloadVpn(scenario)}
                            disabled={busy}
                          >
                            VPN config
                          </Action>
                          <button
                            type="button"
                            onClick={() => stop(scenario)}
                            disabled={busy}
                            className="inline-flex min-h-9 items-center gap-2 rounded-md border border-clay/25 px-3 text-xs font-bold text-clay hover:bg-clay/10 disabled:opacity-50"
                          >
                            <X size={15} />Stop
                          </button>
                        </>
                      )
                      : (
                        <>
                          <Action
                            icon={busy ? LoaderCircle : Play}
                            spinning={busy}
                            onClick={() => start(scenario)}
                            disabled={busy}
                          >
                            {busy ? "Starting" : "Start"}
                          </Action>
                          <button
                            type="button"
                            onClick={() => edit(scenario)}
                            className="inline-flex min-h-9 items-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50"
                          >
                            <Edit3 size={15} />Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => remove(scenario)}
                            className="inline-flex min-h-9 items-center gap-2 rounded-md border border-clay/25 px-3 text-xs font-bold text-clay hover:bg-clay/10"
                          >
                            <Trash2 size={15} />Remove
                          </button>
                        </>
                      )}
                  </div>
                </div>
              );
            })
            : (
              <p className="p-6 text-center text-sm text-ink/54">
                No personal scenarios yet.
              </p>
            )}
        </div>
      </Panel>
    </div>
  );
}

export default function StudentPortal(
  { apiUrl, view }: { apiUrl: string; view: string },
) {
  const [data, setData] = useState<StudentDashboard | null>(null);
  const [error, setError] = useState("");
  const [busyLab, setBusyLab] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [reportLog, setReportLog] = useState("");
  const [scenarios, setScenarios] = useState<ApiScenario[]>([]);
  const [openLabId, setOpenLabId] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    getStudentDashboard(apiUrl).then((dashboard) => {
      if (active) {
        setData(dashboard);
        setScenarios(dashboard.scenarios);
      }
    }).catch((reason) =>
      active &&
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to load your workspace.",
      )
    );
    return () => {
      active = false;
    };
  }, [apiUrl]);
  function downloadConfig(filename: string, config: string) {
    const url = URL.createObjectURL(new Blob([config], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
  function setLabStatus(
    labId: string,
    status: ApiLab["status"],
    nextStep: string,
    labCidr: string | null = null,
  ) {
    setData((current) =>
      current
        ? {
          ...current,
          assignments: current.assignments.map((lab) =>
            lab.id === labId
              ? { ...lab, status, next_step: nextStep, lab_cidr: labCidr }
              : lab
          ),
        }
        : current
    );
  }
  function setLabQuestions(labId: string, questions: ApiLab["questions"]) {
    setData((current) =>
      current
        ? {
          ...current,
          assignments: current.assignments.map((lab) =>
            lab.id === labId
              ? {
                ...lab,
                questions,
                tasks: questions.map((item) => item.prompt),
              }
              : lab
          ),
        }
        : current
    );
  }
  function setLabSubmission(labId: string, score: number, maxScore: number) {
    setData((current) =>
      current
        ? {
          ...current,
          assignments: current.assignments.map((lab) =>
            lab.id === labId
              ? {
                ...lab,
                submission_status: "awaiting_review",
                score,
                max_score: maxScore,
              }
              : lab
          ),
        }
        : current
    );
  }
  async function start(lab: ApiLab) {
    setBusyLab(lab.id);
    setNotice("");
    try {
      const result = await startLab(apiUrl, lab.id);
      setLabStatus(
        lab.id,
        "running",
        "Download the VPN config and connect with WireGuard",
        result.lab_cidr,
      );
      setNotice(result.message);
    } catch (reason) {
      setNotice(
        reason instanceof Error ? reason.message : "Unable to start the lab.",
      );
    } finally {
      setBusyLab(null);
    }
  }
  async function download(lab: ApiLab) {
    setBusyLab(lab.id);
    setNotice("");
    try {
      const result = await getLabVpn(apiUrl, lab.id);
      downloadConfig(result.wireguard_filename, result.wireguard_config);
      setLabStatus(
        lab.id,
        "running",
        "Download the VPN config and connect with WireGuard",
        result.lab_cidr,
      );
      setNotice("Downloaded " + result.wireguard_filename + ".");
    } catch (reason) {
      setNotice(
        reason instanceof Error
          ? reason.message
          : "Unable to download the VPN config.",
      );
    } finally {
      setBusyLab(null);
    }
  }
  async function report(lab: ApiLab, reportType: ReportType) {
    setBusyLab(lab.id);
    setNotice("");
    try {
      const sessions = await listLabSessions(apiUrl, lab.id);
      const latest = [...sessions].sort((left, right) =>
        Date.parse(right.started_at) - Date.parse(left.started_at)
      )[0];
      if (!latest) {
        setNotice(
          "No sessions are available for " + lab.name +
            ". Run the lab once before generating a report.",
        );
        return;
      }
      const [result] = await Promise.all([
        getAttackReport(apiUrl, latest.id),
        openAttackReport(apiUrl, latest.id, reportType),
      ]);
      setReportLog(formatAttackReport(result));
      setNotice("Opened the " + reportType + " report in a new page.");
    } catch (reason) {
      setNotice(
        reason instanceof Error
          ? reason.message
          : "Unable to generate the attack-chain PDF report.",
      );
    } finally {
      setBusyLab(null);
    }
  }
  async function stop(lab: ApiLab) {
    setBusyLab(lab.id);
    setNotice("");
    try {
      await stopLab(apiUrl, lab.id);
      setLabStatus(lab.id, "ready", "Start the lab when you are ready");
      setNotice(lab.name + " has been stopped.");
    } catch (reason) {
      setNotice(
        reason instanceof Error ? reason.message : "Unable to stop the lab.",
      );
    } finally {
      setBusyLab(null);
    }
  }
  if (error) {
    return (
      <p className="rounded-lg border border-clay/25 bg-clay/10 p-4 text-sm font-semibold text-clay">
        {error}
      </p>
    );
  }
  if (!data) {
    return (
      <p className="rounded-lg border border-ink/10 bg-white p-8 text-center text-sm font-semibold text-ink/58">
        Loading your learning workspace...
      </p>
    );
  }
  const reportPanel = reportLog
    ? (
      <Panel eyebrow="Telemetry report" title="Attack chain reconstruction">
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap bg-ink p-4 text-xs leading-5 text-white">{reportLog}</pre>
      </Panel>
    )
    : null;
  const labs = (
    <Panel eyebrow="Assigned labs" title="Continue learning">
      <LabRows
        labs={data.assignments}
        machines={data.machines}
        onOpen={(lab) => {
          setOpenLabId(lab.id);
          setReportLog("");
        }}
      />
    </Panel>
  );
  const builder = (
    <Builder
      apiUrl={apiUrl}
      machines={data.machines}
      scenarios={scenarios}
      onSaved={(scenario) => {
        setScenarios((items) => [scenario, ...items]);
        setNotice(scenario.name + " has been saved to your workspace.");
      }}
      onUpdated={(scenario) => {
        setScenarios((items) =>
          items.map((item) => item.id === scenario.id ? scenario : item)
        );
        setNotice(scenario.name + " has been updated.");
      }}
      onDeleted={(scenarioId, message) => {
        setScenarios((items) => items.filter((item) => item.id !== scenarioId));
        setNotice(message);
      }}
    />
  );
  const library = (
    <Panel eyebrow="Machine library" title="Approved environments">
      <div className="grid divide-y divide-ink/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
        {data.machines.map((machine) => (
          <div key={machine.id} className="p-4">
            <div className="flex items-center justify-between">
              <span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy">
                <ServerCog size={19} />
              </span>
              <span className="rounded-md bg-cloud px-2 py-1 text-xs font-bold text-ink/55">
                {machine.os_type}
              </span>
            </div>
            <p className="mt-4 text-sm font-black text-ink">{machine.name}</p>
            <p className="mt-1 text-xs leading-5 text-ink/54">
              {machine.description}
            </p>
            <p className="mt-3 truncate text-xs font-semibold text-fern">
              {machine.imageUrl}
            </p>
          </div>
        ))}
      </div>
    </Panel>
  );
  const openLab = data.assignments.find((lab) => lab.id === openLabId);
  const workspace = openLab
    ? (
      <LabWorkspace
        apiUrl={apiUrl}
        lab={openLab}
        machines={data.machines}
        busy={busyLab === openLab.id}
        reportLog={reportLog}
        onClose={() => {
          setOpenLabId(null);
          setReportLog("");
        }}
        onStart={start}
        onStop={stop}
        onDownloadVpn={download}
        onReport={report}
        onAnswersSaved={setLabQuestions}
        onSubmitted={setLabSubmission}
      />
    )
    : null;
  if (view === "Assigned labs") {
    return (
      <div className="space-y-4">
        {workspace}
        {notice
          ? (
            <p className="rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">
              {notice}
            </p>
          )
          : null}
        {reportPanel}
        {labs}
      </div>
    );
  }
  if (view === "My scenarios") {
    return (
      <div className="space-y-4">
        {notice
          ? (
            <p className="rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">
              {notice}
            </p>
          )
          : null}
        {builder}
      </div>
    );
  }
  if (view === "Machine library") return library;
  return (
    <div className="space-y-6">
      {workspace}
      {notice
        ? (
          <p className="rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">
            {notice}
          </p>
        )
        : null}
      <div className="grid gap-4 md:grid-cols-2">
        {[[
          "Assigned labs",
          String(data.assignments.length),
          "VPN configs available",
          Download,
        ], [
          "Personal scenarios",
          String(scenarios.length),
          "saved workspaces",
          Layers3,
        ]].map(([label, value, detail, Icon]) => {
          const Metric = Icon as typeof Activity;
          return (
            <div
              key={label as string}
              className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm"
            >
              <div className="flex justify-between">
                <div>
                  <p className="text-sm font-semibold text-ink/55">
                    {label as string}
                  </p>
                  <p className="mt-2 text-3xl font-black text-ink">
                    {value as string}
                  </p>
                </div>
                <span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy">
                  <Metric size={20} />
                </span>
              </div>
              <p className="mt-3 text-xs font-bold text-fern">
                {detail as string}
              </p>
            </div>
          );
        })}
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        {labs}
        <Panel eyebrow="Recent activity" title="Lab updates">
          <div className="divide-y divide-ink/10">
            {data.activity.map((item) => (
              <div key={item.id} className="flex gap-3 p-4">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-cloud text-fern">
                  <Clock3 size={16} />
                </span>
                <div>
                  <p className="text-sm font-black text-ink">{item.title}</p>
                  <p className="mt-1 text-xs text-ink/54">{item.detail}</p>
                  <p className="mt-2 text-xs font-semibold text-ink/42">
                    {item.when}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      {builder}
    </div>
  );
}
