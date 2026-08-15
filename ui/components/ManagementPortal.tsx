"use client";

import { FormEvent, useEffect, useState } from "react";
import clsx from "clsx";
import {
  Activity,
  Check,
  ClipboardCheck,
  Download,
  Edit3,
  Layers3,
  LoaderCircle,
  Play,
  Plus,
  Save,
  ServerCog,
  Square,
  Trash2,
  Users,
  X,
} from "lucide-react";
import {
  type AdminDashboard,
  type ApiLab,
  type ApiLabSession,
  type ApiMachine,
  type ApiStudentGroup,
  type AttackReport,
  changeSetting,
  changeUserRole,
  completeReview,
  createAdminMachine,
  createTeacherGroup,
  createTeacherLab,
  deleteTeacherGroup,
  deleteTeacherLab,
  discoverGitHubMachines,
  downloadAttackReport,
  getAdminDashboard,
  getAttackReport,
  getLabVpn,
  getTeacherDashboard,
  type GitHubMachineFolder,
  type GitHubMachineImportInput,
  type GradingTask,
  importGitHubMachine,
  listLabSessions,
  type MachineInput,
  refreshGitHubMachine,
  type ReportType,
  startLab,
  startLabStream,
  stopLab,
  stopLabStream,
  type TeacherDashboard,
  type TeacherLabInput,
  updateAdminMachine,
  updateTeacherGroup,
  updateTeacherLab,
} from "@/lib/api";

function Panel(
  { eyebrow, title, children, action }: {
    eyebrow: string;
    title: string;
    children: React.ReactNode;
    action?: React.ReactNode;
  },
) {
  return (
    <section className="rounded-lg border border-ink/10 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 p-4">
        <div>
          <p className="text-xs font-bold uppercase text-ink/44">{eyebrow}</p>
          <h2 className="mt-1 text-xl font-black text-ink">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Button(
  { children, icon: Icon, onClick, disabled, spinning }: {
    children: React.ReactNode;
    icon: typeof Plus;
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
      {children}
    </button>
  );
}

function Notice({ text }: { text: string }) {
  return text
    ? (
      <p className="mb-5 rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">
        {text}
      </p>
    )
    : null;
}

function downloadConfig(filename: string, config: string) {
  const url = URL.createObjectURL(new Blob([config], { type: "text/plain" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function formatAttackReport(report: AttackReport) {
  const lines = [
    "Session: " + report.session_id,
    "Generated: " + report.generated_at,
    "Telemetry events analyzed: " + report.telemetry_event_count,
    "Explicit detections: " + report.event_count,
    "",
    report.summary,
    "",
    "Attack chain",
  ];
  report.attack_chain.forEach((phase, index) => {
    lines.push(
      (index + 1) + ". " + phase.tactic + " - " + phase.technique_id + " - " +
        phase.technique + " (" + phase.event_count + " events)",
    );
    lines.push("   " + phase.rationale);
    phase.evidence.slice(0, 3).forEach((item) =>
      lines.push("   evidence: " + JSON.stringify(item))
    );
  });
  return lines.join("\n");
}

function latestSession(sessions: ApiLabSession[]) {
  return [...sessions].sort((left, right) =>
    Date.parse(right.started_at) - Date.parse(left.started_at)
  )[0];
}

type LabDraft = {
  name: string;
  description: string;
  machine_ids: string[];
  tasks: GradingTask[];
  student_ids: string[];
  group_ids: string[];
  status: ApiLab["status"];
};

const emptyTask: GradingTask = {
  prompt: "",
  grading_type: "exact",
  expected_answer: "",
  points: 1,
};
const emptyLabDraft: LabDraft = {
  name: "",
  description: "",
  machine_ids: [],
  tasks: [{ ...emptyTask }],
  student_ids: [],
  group_ids: [],
  status: "ready",
};

function LabForm({
  machines,
  students = [],
  groups = [],
  value,
  onChange,
  onSubmit,
  submitLabel,
  saving,
}: {
  machines: ApiMachine[];
  students?: TeacherDashboard["students"];
  groups?: ApiStudentGroup[];
  value: LabDraft;
  onChange: (value: LabDraft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitLabel: string;
  saving?: boolean;
}) {
  function toggleMachine(id: string) {
    onChange({
      ...value,
      machine_ids: value.machine_ids.includes(id)
        ? value.machine_ids.filter((item) => item !== id)
        : [...value.machine_ids, id],
    });
  }

  function toggleStudent(id: string) {
    onChange({
      ...value,
      student_ids: value.student_ids.includes(id)
        ? value.student_ids.filter((item) => item !== id)
        : [...value.student_ids, id],
    });
  }

  function toggleGroup(id: string) {
    onChange({
      ...value,
      group_ids: value.group_ids.includes(id)
        ? value.group_ids.filter((item) => item !== id)
        : [...value.group_ids, id],
    });
  }

  function updateTask(index: number, patch: Partial<GradingTask>) {
    onChange({
      ...value,
      tasks: value.tasks.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item
      ),
    });
  }

  function removeTask(index: number) {
    onChange({
      ...value,
      tasks: value.tasks.filter((_, itemIndex) => itemIndex !== index),
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5 p-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(180px,0.75fr)_minmax(260px,1.25fr)]">
        <label className="text-sm font-bold text-ink/72">
          Lab name<input
            value={value.name}
            onChange={(event) =>
              onChange({ ...value, name: event.target.value })}
            className="mt-2 min-h-11 w-full rounded-md border border-ink/15 px-3 text-sm font-semibold text-ink outline-none focus:border-fern"
            placeholder="e.g. Suspicious payroll portal"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Scenario description<textarea
            value={value.description}
            onChange={(event) =>
              onChange({ ...value, description: event.target.value })}
            className="mt-2 min-h-28 w-full resize-y rounded-md border border-ink/15 px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-fern"
            placeholder="Tell the story: the company, the environment, what machines are involved, and what students need to investigate."
          />
        </label>
      </div>
      <div>
        <p className="text-sm font-black text-ink">Machines in this lab</p>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {machines.map((machine) => {
            const selected = value.machine_ids.includes(machine.id);
            return (
              <button
                key={machine.id}
                type="button"
                onClick={() => toggleMachine(machine.id)}
                className={clsx(
                  "rounded-md border p-3 text-left transition",
                  selected
                    ? "border-fern bg-mint/10"
                    : "border-ink/10 hover:border-fern/50",
                )}
              >
                <span className="flex items-center justify-between gap-2">
                  <ServerCog size={18} className="text-canopy" />
                  <span
                    className={clsx(
                      "grid h-5 w-5 place-items-center rounded-full",
                      selected
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
      </div>
      <div>
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-black text-ink">
            Student flags and questions
          </p>
          <button
            type="button"
            onClick={() =>
              onChange({ ...value, tasks: [...value.tasks, { ...emptyTask }] })}
            className="inline-flex min-h-9 items-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50"
          >
            <Plus size={15} />Add question
          </button>
        </div>
        <div className="mt-3 space-y-3">
          {value.tasks.map((task, index) => (
            <div key={index} className="rounded-md border border-ink/10 p-3">
              <div className="grid gap-2 sm:grid-cols-[auto_1fr_auto] sm:items-center">
                <span className="text-xs font-bold text-ink/45">
                  #{index + 1}
                </span>
                <input
                  value={task.prompt}
                  onChange={(event) =>
                    updateTask(index, { prompt: event.target.value })}
                  className="min-h-10 rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
                  placeholder="e.g. What service exposes the payroll login?"
                />
                {value.tasks.length > 1
                  ? (
                    <button
                      type="button"
                      onClick={() => removeTask(index)}
                      className="inline-flex min-h-10 items-center justify-center rounded-md border border-clay/25 px-3 text-clay hover:bg-clay/10"
                    >
                      <Trash2 size={16} />
                    </button>
                  )
                  : null}
              </div>
              <div className="mt-2 grid gap-2 sm:grid-cols-[160px_1fr_100px]">
                <label className="text-xs font-bold text-ink/55">
                  Grading<select
                    value={task.grading_type}
                    onChange={(event) =>
                      updateTask(index, {
                        grading_type: event.target
                          .value as GradingTask["grading_type"],
                      })}
                    className="mt-1 min-h-10 w-full rounded-md border border-ink/15 px-2 text-sm"
                  >
                    <option value="exact">Exact answer</option>
                    <option value="contains">Contains text</option>
                    <option value="regex">Regular expression</option>
                    <option value="manual">Manual review</option>
                  </select>
                </label>
                <label className="text-xs font-bold text-ink/55">
                  Expected answer or pattern<input
                    value={task.expected_answer}
                    disabled={task.grading_type === "manual"}
                    onChange={(event) =>
                      updateTask(index, {
                        expected_answer: event.target.value,
                      })}
                    className="mt-1 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm disabled:bg-cloud"
                    placeholder={task.grading_type === "regex"
                      ? "e.g. FLAG\\{[A-Z0-9]+\\}"
                      : "Answer hidden from students"}
                  />
                </label>
                <label className="text-xs font-bold text-ink/55">
                  Points<input
                    type="number"
                    min={1}
                    max={100}
                    value={task.points}
                    onChange={(event) =>
                      updateTask(index, {
                        points: Math.max(
                          1,
                          Math.min(100, Number(event.target.value) || 1),
                        ),
                      })}
                    className="mt-1 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm"
                  />
                </label>
              </div>
            </div>
          ))}
        </div>
      </div>
      {students.length || groups.length
        ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <p className="text-sm font-black text-ink">Assign to groups</p>
              <div className="mt-3 grid gap-2">
                {groups.length
                  ? groups.map((group) => (
                    <label
                      key={group.id}
                      className={clsx(
                        "flex min-h-11 items-center justify-between gap-3 rounded-md border px-3 text-sm font-bold",
                        value.group_ids.includes(group.id)
                          ? "border-fern bg-mint/10 text-fern"
                          : "border-ink/10 text-ink/65",
                      )}
                    >
                      <span>
                        {group.name}
                        <span className="ml-2 text-xs font-semibold text-ink/45">
                          {group.student_count} students
                        </span>
                      </span>
                      <input
                        type="checkbox"
                        checked={value.group_ids.includes(group.id)}
                        onChange={() => toggleGroup(group.id)}
                        className="h-4 w-4 accent-[#2f6f5f]"
                      />
                    </label>
                  ))
                  : (
                    <p className="rounded-md bg-cloud p-3 text-sm font-semibold text-ink/54">
                      Create a student group first.
                    </p>
                  )}
              </div>
            </div>
            <div>
              <p className="text-sm font-black text-ink">
                Assign individual students
              </p>
              <div className="mt-3 grid gap-2">
                {students.map((student) => (
                  <label
                    key={student.id}
                    className={clsx(
                      "flex min-h-11 items-center justify-between gap-3 rounded-md border px-3 text-sm font-bold",
                      value.student_ids.includes(student.id)
                        ? "border-fern bg-mint/10 text-fern"
                        : "border-ink/10 text-ink/65",
                    )}
                  >
                    <span>
                      {student.name}
                      <span className="ml-2 text-xs font-semibold text-ink/45">
                        {student.cohort}
                      </span>
                    </span>
                    <input
                      type="checkbox"
                      checked={value.student_ids.includes(student.id)}
                      onChange={() => toggleStudent(student.id)}
                      className="h-4 w-4 accent-[#2f6f5f]"
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>
        )
        : null}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink/10 pt-4">
        <label className="flex min-h-10 items-center gap-2 text-sm font-bold text-ink/65">
          <input
            type="checkbox"
            checked={value.status !== "locked"}
            onChange={(event) =>
              onChange({
                ...value,
                status: event.target.checked ? "ready" : "locked",
              })}
            className="h-4 w-4 accent-[#2f6f5f]"
          />{" "}
          Publish for assigned students
        </label>
        <button
          disabled={saving || !value.name.trim() ||
            value.description.trim().length < 10 || !value.machine_ids.length}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-canopy px-3 text-sm font-bold text-white disabled:opacity-50"
        >
          <Save size={16} />
          {saving ? "Saving" : submitLabel}
        </button>
      </div>
    </form>
  );
}

function LabList({
  labs,
  machines,
  students = [],
  groups = [],
  editable = false,
  onSave,
  onDelete,
  onStart,
  onStop,
  onDownloadVpn,
  onReport,
}: {
  labs: ApiLab[];
  machines: ApiMachine[];
  students?: TeacherDashboard["students"];
  groups?: ApiStudentGroup[];
  editable?: boolean;
  onSave?: (lab: ApiLab) => Promise<void>;
  onDelete?: (lab: ApiLab) => Promise<void>;
  onStart?: (lab: ApiLab) => Promise<void>;
  onStop?: (lab: ApiLab) => Promise<void>;
  onDownloadVpn?: (lab: ApiLab) => Promise<void>;
  onReport?: (lab: ApiLab, reportType: ReportType) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<LabDraft>(emptyLabDraft);
  const [busyId, setBusyId] = useState<string | null>(null);

  function beginEdit(lab: ApiLab) {
    setEditingId(lab.id);
    setDraft({
      name: lab.name,
      description: lab.description,
      machine_ids: lab.machine_ids,
      tasks: lab.grading_tasks?.length
        ? lab.grading_tasks
        : lab.tasks.map((prompt) => ({ ...emptyTask, prompt })),
      student_ids: lab.student_ids ?? [],
      group_ids: lab.group_ids ?? [],
      status: lab.status,
    });
  }

  async function save(lab: ApiLab) {
    if (
      !onSave || !draft.name.trim() || draft.description.trim().length < 10 ||
      !draft.machine_ids.length
    ) return;
    setBusyId(lab.id);
    try {
      await onSave({
        ...lab,
        name: draft.name.trim(),
        description: draft.description.trim(),
        machine_ids: draft.machine_ids,
        grading_tasks: draft.tasks.filter((task) => task.prompt.trim()).map((
          task,
        ) => ({
          ...task,
          prompt: task.prompt.trim(),
          expected_answer: task.expected_answer.trim(),
        })),
        student_ids: draft.student_ids,
        group_ids: draft.group_ids,
        status: draft.status,
      });
      setEditingId(null);
    } finally {
      setBusyId(null);
    }
  }

  async function remove(lab: ApiLab) {
    if (!onDelete || !window.confirm("Remove " + lab.name + "?")) return;
    setBusyId(lab.id);
    try {
      await onDelete(lab);
    } finally {
      setBusyId(null);
    }
  }

  async function start(lab: ApiLab) {
    if (!onStart) return;
    setBusyId(lab.id);
    try {
      await onStart(lab);
    } finally {
      setBusyId(null);
    }
  }

  async function stop(lab: ApiLab) {
    if (!onStop) return;
    setBusyId(lab.id);
    try {
      await onStop(lab);
    } finally {
      setBusyId(null);
    }
  }

  async function downloadVpn(lab: ApiLab) {
    if (!onDownloadVpn) return;
    setBusyId(lab.id);
    try {
      await onDownloadVpn(lab);
    } finally {
      setBusyId(null);
    }
  }

  async function report(lab: ApiLab, reportType: ReportType) {
    if (!onReport) return;
    setBusyId(lab.id);
    try {
      await onReport(lab, reportType);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="divide-y divide-ink/10">
      {labs.length
        ? labs.map((lab) => {
          const isEditing = editingId === lab.id;
          const disabled = busyId === lab.id;
          return (
            <div key={lab.id} className="p-4">
              {isEditing
                ? (
                  <div className="space-y-3">
                    <LabForm
                      machines={machines}
                      students={students}
                      groups={groups}
                      value={draft}
                      onChange={setDraft}
                      submitLabel="Save lab"
                      saving={disabled}
                      onSubmit={(event) => {
                        event.preventDefault();
                        save(lab);
                      }}
                    />
                    <div className="flex flex-wrap justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-sm font-bold text-ink/65 hover:border-fern/50"
                      >
                        <X size={16} />Cancel
                      </button>
                    </div>
                  </div>
                )
                : (
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0">
                      <p className="text-sm font-black text-ink">{lab.name}</p>
                      <p className="mt-1 text-xs text-ink/54">
                        {lab.description || "No description yet."}
                      </p>
                      <p className="mt-2 text-xs font-semibold text-ink/42">
                        {lab.level} - {lab.runtime} - {lab.owner} -{" "}
                        {lab.machine_ids.length} machines - {lab.tasks.length}
                        {" "}
                        questions - {lab.assigned_count ?? 0} assigned
                      </p>
                      {lab.tasks.length
                        ? (
                          <ul className="mt-3 grid gap-1 text-xs text-ink/55">
                            {lab.tasks.slice(0, 3).map((task) => (
                              <li key={task} className="flex gap-2">
                                <Check
                                  size={14}
                                  className="mt-0.5 shrink-0 text-fern"
                                />
                                {task}
                              </li>
                            ))}
                          </ul>
                        )
                        : null}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      <span
                        className={clsx(
                          "rounded-full px-2.5 py-1 text-xs font-bold",
                          lab.status === "locked"
                            ? "bg-cloud text-ink/55"
                            : "bg-mint/20 text-fern",
                        )}
                      >
                        {lab.status === "locked" ? "Draft" : "Published"}
                      </span>
                      <Button
                        icon={disabled ? LoaderCircle : ClipboardCheck}
                        spinning={disabled}
                        onClick={() => report(lab, "academic")}
                        disabled={disabled || !onReport}
                      >
                        {disabled ? "Loading" : "Academic report"}
                      </Button>
                      <Button
                        icon={disabled ? LoaderCircle : ClipboardCheck}
                        spinning={disabled}
                        onClick={() => report(lab, "professional")}
                        disabled={disabled || !onReport}
                      >
                        {disabled ? "Loading" : "Professional report"}
                      </Button>
                      {onStart || onStop
                        ? lab.status === "running"
                          ? (
                            <>
                              <Button
                                icon={disabled ? LoaderCircle : Download}
                                spinning={disabled}
                                onClick={() => downloadVpn(lab)}
                                disabled={disabled || !onDownloadVpn}
                              >
                                {disabled ? "Preparing" : "Get VPN"}
                              </Button>
                              <button
                                type="button"
                                onClick={() => stop(lab)}
                                disabled={disabled}
                                className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-clay/25 px-3 text-xs font-bold text-clay hover:bg-clay/10 disabled:opacity-50"
                              >
                                {disabled
                                  ? (
                                    <LoaderCircle
                                      size={15}
                                      className="animate-spin"
                                    />
                                  )
                                  : <Square size={15} />}Stop
                              </button>
                            </>
                          )
                          : (
                            <Button
                              icon={disabled ? LoaderCircle : Play}
                              spinning={disabled}
                              onClick={() => start(lab)}
                              disabled={disabled || lab.status === "locked"}
                            >
                              {disabled ? "Starting" : "Start"}
                            </Button>
                          )
                        : null}
                      {editable
                        ? (
                          <>
                            <button
                              type="button"
                              onClick={() => beginEdit(lab)}
                              disabled={disabled}
                              className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50 disabled:opacity-50"
                            >
                              <Edit3 size={15} />Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => remove(lab)}
                              disabled={disabled}
                              className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-clay/25 px-3 text-xs font-bold text-clay hover:bg-clay/10 disabled:opacity-50"
                            >
                              <Trash2 size={15} />Remove
                            </button>
                          </>
                        )
                        : null}
                    </div>
                  </div>
                )}
            </div>
          );
        })
        : (
          <p className="p-6 text-center text-sm font-semibold text-ink/54">
            No labs yet.
          </p>
        )}
    </div>
  );
}

function TeacherPortal({ apiUrl, view }: { apiUrl: string; view: string }) {
  const [data, setData] = useState<TeacherDashboard | null>(null);
  const [labs, setLabs] = useState<ApiLab[]>([]);
  const [reviews, setReviews] = useState<TeacherDashboard["reviews"]>([]);
  const [groups, setGroups] = useState<ApiStudentGroup[]>([]);
  const [notice, setNotice] = useState("");
  const [processLog, setProcessLog] = useState("");
  const [newLab, setNewLab] = useState<LabDraft>(emptyLabDraft);
  const [saving, setSaving] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupStudents, setGroupStudents] = useState<string[]>([]);
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  useEffect(() => {
    getTeacherDashboard(apiUrl).then((dashboard) => {
      setData(dashboard);
      setLabs(dashboard.labs);
      setReviews(dashboard.reviews);
      setGroups(dashboard.groups);
      setNewLab((draft) => ({
        ...draft,
        machine_ids: draft.machine_ids.length
          ? draft.machine_ids
          : dashboard.machines.slice(0, 2).map((machine) => machine.id),
      }));
    }).catch((error) =>
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to load teaching workspace.",
      )
    );
  }, [apiUrl]);
  async function createLab(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !newLab.name.trim() || newLab.description.trim().length < 10 ||
      !newLab.machine_ids.length
    ) {
      setNotice(
        "Add a lab name, scenario description, and at least one machine.",
      );
      return;
    }
    setSaving(true);
    try {
      const payload: TeacherLabInput = {
        name: newLab.name.trim(),
        description: newLab.description.trim(),
        machine_ids: newLab.machine_ids,
        tasks: newLab.tasks.filter((task) => task.prompt.trim()).map((
          task,
        ) => ({
          ...task,
          prompt: task.prompt.trim(),
          expected_answer: task.expected_answer.trim(),
        })),
        student_ids: newLab.student_ids,
        group_ids: newLab.group_ids,
        publish: newLab.status !== "locked",
      };
      const lab = await createTeacherLab(apiUrl, payload);
      setLabs((items) => [lab, ...items]);
      setNewLab({
        ...emptyLabDraft,
        tasks: [{ ...emptyTask }],
        machine_ids: data?.machines.slice(0, 2).map((machine) => machine.id) ??
          [],
      });
      setNotice(lab.name + " has been created.");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to create the lab.",
      );
    } finally {
      setSaving(false);
    }
  }
  async function saveLab(lab: ApiLab) {
    try {
      const updated = await updateTeacherLab(apiUrl, lab);
      setLabs((items) =>
        items.map((item) => item.id === updated.id ? updated : item)
      );
      setNotice(updated.name + " has been updated.");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to update the lab.",
      );
      throw error;
    }
  }
  async function removeLab(lab: ApiLab) {
    try {
      const result = await deleteTeacherLab(apiUrl, lab.id);
      setLabs((items) => items.filter((item) => item.id !== lab.id));
      setReviews((items) => items.filter((item) => item.lab !== lab.name));
      setNotice(result.message);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to remove the lab.",
      );
      throw error;
    }
  }
  async function startManagedLab(lab: ApiLab) {
    try {
      const result = await startLab(apiUrl, lab.id);
      setLabs((items) =>
        items.map((item) =>
          item.id === lab.id
            ? {
              ...item,
              status: "running",
              next_step: "Lab containers are running.",
            }
            : item
        )
      );
      setNotice(result.message);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to start the lab.",
      );
    }
  }
  async function stopManagedLab(lab: ApiLab) {
    try {
      await stopLab(apiUrl, lab.id);
      setLabs((items) =>
        items.map((item) =>
          item.id === lab.id
            ? {
              ...item,
              status: "ready",
              next_step: "Start the lab when you are ready",
            }
            : item
        )
      );
      setNotice(lab.name + " has been stopped.");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to stop the lab.",
      );
    }
  }
  async function downloadManagedVpn(lab: ApiLab) {
    try {
      const result = await getLabVpn(apiUrl, lab.id);
      downloadConfig(result.wireguard_filename, result.wireguard_config);
      setNotice("Downloaded " + result.wireguard_filename + ".");
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to download the VPN config.",
      );
    }
  }
  async function loadManagedReport(lab: ApiLab, reportType: ReportType) {
    try {
      const latest = latestSession(await listLabSessions(apiUrl, lab.id));
      if (!latest) {
        setNotice("No sessions are available for " + lab.name + ".");
        return;
      }
      const [report, pdfDocument] = await Promise.all([
        getAttackReport(apiUrl, latest.id),
        downloadAttackReport(apiUrl, latest.id, reportType),
      ]);
      setProcessLog(formatAttackReport(report));
      downloadBlob(pdfDocument.filename, pdfDocument.blob);
      setNotice("Downloaded " + pdfDocument.filename + ".");
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to generate the attack-chain PDF report.",
      );
    }
  }
  async function review(id: string) {
    const item = reviews.find((candidate) => candidate.id === id);
    if (!item) return;
    const scoreText = window.prompt(
      "Final score out of " + item.max_score,
      String(item.auto_score),
    );
    if (scoreText === null) return;
    const score = Number(scoreText);
    if (!Number.isInteger(score) || score < 0 || score > item.max_score) {
      setNotice(
        "Enter a whole-number score between 0 and " + item.max_score + ".",
      );
      return;
    }
    const feedback =
      window.prompt("Teacher feedback (optional)", item.feedback) ?? "";
    try {
      const result = await completeReview(apiUrl, id, score, feedback);
      setReviews((items) => items.filter((reviewItem) => reviewItem.id !== id));
      setNotice(result.message);
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to finalize the submission.",
      );
    }
  }
  function toggleGroupStudent(id: string) {
    setGroupStudents((items) =>
      items.includes(id) ? items.filter((item) => item !== id) : [...items, id]
    );
  }
  function editGroup(group: ApiStudentGroup) {
    setEditingGroupId(group.id);
    setGroupName(group.name);
    setGroupStudents(group.student_ids);
  }
  function resetGroupForm() {
    setEditingGroupId(null);
    setGroupName("");
    setGroupStudents([]);
  }
  async function saveGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!groupName.trim()) return;
    try {
      const payload = { name: groupName.trim(), student_ids: groupStudents };
      const group = editingGroupId
        ? await updateTeacherGroup(apiUrl, editingGroupId, payload)
        : await createTeacherGroup(apiUrl, payload);
      setGroups((items) =>
        editingGroupId
          ? items.map((item) => item.id === group.id ? group : item)
          : [group, ...items]
      );
      resetGroupForm();
      const dashboard = await getTeacherDashboard(apiUrl);
      setData(dashboard);
      setLabs(dashboard.labs);
      setReviews(dashboard.reviews);
      setGroups(dashboard.groups);
      setNotice(group.name + " has been saved.");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to save the group.",
      );
    }
  }
  async function removeGroup(group: ApiStudentGroup) {
    if (!window.confirm("Remove " + group.name + "?")) return;
    try {
      const result = await deleteTeacherGroup(apiUrl, group.id);
      setGroups((items) => items.filter((item) => item.id !== group.id));
      const dashboard = await getTeacherDashboard(apiUrl);
      setData(dashboard);
      setLabs(dashboard.labs);
      setReviews(dashboard.reviews);
      setGroups(dashboard.groups);
      setNotice(result.message);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to remove the group.",
      );
    }
  }
  if (!data) {
    return (
      <p className="rounded-lg border border-ink/10 bg-white p-8 text-center text-sm font-semibold text-ink/58">
        Loading teaching workspace...
      </p>
    );
  }
  const library = (
    <Panel eyebrow="Machine library" title="Approved environments">
      <div className="grid divide-y divide-ink/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
        {data.machines.map((machine) => (
          <MachineCard key={machine.id} machine={machine} />
        ))}
      </div>
    </Panel>
  );
  const logPanel = processLog
    ? (
      <Panel eyebrow="Telemetry report" title="Attack chain reconstruction">
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap bg-ink p-4 text-xs leading-5 text-white">{processLog}</pre>
      </Panel>
    )
    : null;
  const groupPanel = (
    <Panel
      eyebrow="Student groups"
      title={editingGroupId ? "Edit group" : "Create group"}
    >
      <form onSubmit={saveGroup} className="space-y-4 p-4">
        <label className="text-sm font-bold text-ink/72">
          Group name<input
            value={groupName}
            onChange={(event) => setGroupName(event.target.value)}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder="Blue team cohort"
          />
        </label>
        <div>
          <p className="text-sm font-black text-ink">Students</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {data.students.map((student) => (
              <label
                key={student.id}
                className={clsx(
                  "flex min-h-11 items-center justify-between gap-3 rounded-md border px-3 text-sm font-bold",
                  groupStudents.includes(student.id)
                    ? "border-fern bg-mint/10 text-fern"
                    : "border-ink/10 text-ink/65",
                )}
              >
                <span>
                  {student.name}
                  <span className="ml-2 text-xs font-semibold text-ink/45">
                    {student.active_labs} labs
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={groupStudents.includes(student.id)}
                  onChange={() => toggleGroupStudent(student.id)}
                  className="h-4 w-4 accent-[#2f6f5f]"
                />
              </label>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap justify-between gap-2 border-t border-ink/10 pt-4">
          {editingGroupId
            ? (
              <button
                type="button"
                onClick={resetGroupForm}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-sm font-bold text-ink/65 hover:border-fern/50"
              >
                <X size={16} />Cancel
              </button>
            )
            : <span />}
          <button
            disabled={!groupName.trim()}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-canopy px-3 text-sm font-bold text-white disabled:opacity-50"
          >
            <Save size={16} />Save group
          </button>
        </div>
      </form>
      <div className="divide-y divide-ink/10">
        {groups.length
          ? groups.map((group) => (
            <div
              key={group.id}
              className="flex flex-wrap items-center justify-between gap-3 p-4"
            >
              <div>
                <p className="text-sm font-black text-ink">{group.name}</p>
                <p className="mt-1 text-xs text-ink/54">
                  {group.student_count} students - {group.lab_count}{" "}
                  assigned labs
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => editGroup(group)}
                  className="inline-flex min-h-9 items-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50"
                >
                  <Edit3 size={15} />Edit
                </button>
                <button
                  type="button"
                  onClick={() => removeGroup(group)}
                  className="inline-flex min-h-9 items-center gap-2 rounded-md border border-clay/25 px-3 text-xs font-bold text-clay hover:bg-clay/10"
                >
                  <Trash2 size={15} />Remove
                </button>
              </div>
            </div>
          ))
          : (
            <p className="p-6 text-center text-sm text-ink/54">
              No groups yet.
            </p>
          )}
      </div>
    </Panel>
  );
  if (view === "Class labs") {
    return (
      <div className="space-y-5">
        <Notice text={notice} />
        {logPanel}
        <Panel eyebrow="Class labs" title="Author and publish labs">
          <LabForm
            machines={data.machines}
            students={data.students}
            groups={groups}
            value={newLab}
            onChange={setNewLab}
            onSubmit={createLab}
            submitLabel="Create lab"
            saving={saving}
          />
          <LabList
            labs={labs}
            machines={data.machines}
            students={data.students}
            groups={groups}
            editable
            onSave={saveLab}
            onDelete={removeLab}
            onStart={startManagedLab}
            onStop={stopManagedLab}
            onDownloadVpn={downloadManagedVpn}
            onReport={loadManagedReport}
          />
        </Panel>
      </div>
    );
  }
  if (view === "Students") {
    return (
      <div>
        <Notice text={notice} />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.95fr)]">
          <Panel eyebrow="Learners" title="Class progress">
            <div className="divide-y divide-ink/10">
              {data.students.map((student) => (
                <div key={student.id} className="p-4">
                  <div className="flex justify-between gap-3">
                    <div>
                      <p className="text-sm font-black text-ink">
                        {student.name}
                      </p>
                      <p className="mt-1 text-xs text-ink/54">
                        {student.cohort} - {student.active_labs} assigned -{" "}
                        {student.running_labs} running
                      </p>
                    </div>
                    <p className="text-sm font-bold text-fern">
                      {student.progress}%
                    </p>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-cloud">
                    <div
                      className="h-full bg-fern"
                      style={{ width: student.progress + "%" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Panel>
          {groupPanel}
          <Panel eyebrow="Review queue" title="Student activity">
            <div className="divide-y divide-ink/10">
              {reviews.length
                ? reviews.map((item) => (
                  <div key={item.id} className="p-4">
                    <p className="text-sm font-black text-ink">
                      {item.student}
                    </p>
                    <p className="mt-1 text-xs text-ink/54">{item.lab}</p>
                    <div className="mt-3 flex items-center justify-between gap-3">
                      <span className="text-xs font-bold text-fern">
                        {item.state}
                      </span>
                      <Button
                        icon={ClipboardCheck}
                        onClick={() => review(item.id)}
                      >
                        Review
                      </Button>
                    </div>
                  </div>
                ))
                : (
                  <p className="p-6 text-center text-sm text-ink/54">
                    Review queue is clear.
                  </p>
                )}
            </div>
          </Panel>
        </div>
      </div>
    );
  }
  if (view === "Machine library") return library;
  return (
    <div>
      <Notice text={notice} />
      {logPanel ? <div className="mb-5">{logPanel}</div> : null}
      <div className="grid gap-4 md:grid-cols-3">
        {[
          [
            "Published labs",
            String(labs.filter((lab) => lab.status !== "locked").length),
            Layers3,
          ],
          ["Active students", String(data.students.length), Users],
          [
            "Running sessions",
            String(data.metrics?.running_sessions ?? 0),
            Activity,
          ],
        ].map(([label, value, Icon]) => {
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
            </div>
          );
        })}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Panel eyebrow="Class labs" title="Your catalogue">
          <LabList
            labs={labs.slice(0, 3)}
            machines={data.machines}
            students={data.students}
            groups={groups}
            editable
            onSave={saveLab}
            onDelete={removeLab}
            onStart={startManagedLab}
            onStop={stopManagedLab}
            onDownloadVpn={downloadManagedVpn}
            onReport={loadManagedReport}
          />
        </Panel>
        <Panel eyebrow="Review queue" title="Needs attention">
          <div className="divide-y divide-ink/10">
            {reviews.slice(0, 3).map((item) => (
              <div key={item.id} className="p-4">
                <p className="text-sm font-black text-ink">{item.student}</p>
                <p className="mt-1 text-xs text-ink/54">{item.lab}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function MachineCard(
  { machine, onEdit, onRefresh }: {
    machine: ApiMachine;
    onEdit?: (machine: ApiMachine) => void;
    onRefresh?: (machine: ApiMachine) => void;
  },
) {
  const detailCount = machine.ports.length + machine.volumes.length +
    Object.keys(machine.environment).length + machine.cap_add.length;
  return (
    <div className="p-4">
      <div className="flex items-center justify-between">
        <span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy">
          <ServerCog size={19} />
        </span>
        <div className="flex gap-2">
          <span className="rounded-md bg-cloud px-2 py-1 text-xs font-bold text-ink/55">
            {machine.source_type}
          </span>
          <span className="rounded-md bg-cloud px-2 py-1 text-xs font-bold text-ink/55">
            {machine.os_type}
          </span>
        </div>
      </div>
      <p className="mt-4 text-sm font-black text-ink">{machine.name}</p>
      <p className="mt-1 text-xs leading-5 text-ink/54">
        {machine.description || "No description provided."}
      </p>
      <p className="mt-3 truncate text-xs font-semibold text-fern">
        {machine.imageUrl}
      </p>
      <p className="mt-2 text-xs font-semibold text-ink/45">
        {machine.restart_policy} - {machine.memory_limit} RAM -{" "}
        {machine.cpu_limit} CPU{machine.privileged ? " - privileged" : ""}
        {detailCount ? " - " + detailCount + " runtime options" : ""}
        {machine.import_version ? " - import v" + machine.import_version : ""}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {onEdit
          ? (
            <button
              type="button"
              onClick={() => onEdit(machine)}
              className="inline-flex min-h-9 items-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50"
            >
              <Edit3 size={15} />Edit
            </button>
          )
          : null}
        {onRefresh && machine.repository_url
          ? (
            <button
              type="button"
              onClick={() => onRefresh(machine)}
              className="inline-flex min-h-9 items-center gap-2 rounded-md border border-fern/25 px-3 text-xs font-bold text-fern hover:bg-mint/10"
            >
              <Download size={15} />Refresh from GitHub
            </button>
          )
          : null}
      </div>
    </div>
  );
}

type MachineDraft = {
  name: string;
  image_url: string;
  source_type: MachineInput["source_type"];
  os_type: string;
  description: string;
  attachment: string;
  hostname: string;
  command: string;
  entrypoint: string;
  working_dir: string;
  run_as: string;
  restart_policy: MachineInput["restart_policy"];
  privileged: boolean;
  tty: boolean;
  stdin_open: boolean;
  ports: string;
  volumes: string;
  environment: string;
  labels: string;
  dns: string;
  extra_hosts: string;
  cap_add: string;
  network_aliases: string;
  detection_profile: string;
  memory_limit: string;
  cpu_limit: number;
};

const emptyMachineDraft: MachineDraft = {
  name: "",
  image_url: "",
  source_type: "dockerhub",
  os_type: "Linux",
  description: "",
  attachment: "",
  hostname: "",
  command: "",
  entrypoint: "",
  working_dir: "",
  run_as: "",
  restart_policy: "unless-stopped",
  privileged: false,
  tty: true,
  stdin_open: false,
  ports: "",
  volumes: "",
  environment: "",
  labels: "",
  dns: "",
  extra_hosts: "",
  cap_add: "",
  network_aliases: "",
  detection_profile: "",
  memory_limit: "512m",
  cpu_limit: 1,
};

function lines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function keyValues(value: string) {
  return Object.fromEntries(
    lines(value).map((item) => {
      const splitAt = item.indexOf("=");
      return splitAt === -1
        ? [item, ""]
        : [item.slice(0, splitAt).trim(), item.slice(splitAt + 1).trim()];
    }).filter(([key]) => key),
  );
}

function machinePayload(draft: MachineDraft): MachineInput {
  return {
    name: draft.name.trim(),
    image_url: draft.image_url.trim(),
    source_type: draft.source_type,
    os_type: draft.os_type,
    description: draft.description.trim(),
    attachment: draft.attachment.trim() || null,
    hostname: draft.hostname.trim() || null,
    command: draft.command.trim() || null,
    entrypoint: draft.entrypoint.trim() || null,
    working_dir: draft.working_dir.trim() || null,
    run_as: draft.run_as.trim() || null,
    restart_policy: draft.restart_policy,
    privileged: draft.privileged,
    tty: draft.tty,
    stdin_open: draft.stdin_open,
    ports: lines(draft.ports),
    volumes: lines(draft.volumes),
    environment: keyValues(draft.environment),
    labels: keyValues(draft.labels),
    dns: lines(draft.dns),
    extra_hosts: lines(draft.extra_hosts),
    cap_add: lines(draft.cap_add),
    network_aliases: lines(draft.network_aliases),
    detection_profile: draft.detection_profile.trim() || null,
    memory_limit: draft.memory_limit,
    cpu_limit: draft.cpu_limit,
  };
}

function machineDraftFrom(machine: ApiMachine): MachineDraft {
  const pairs = (items: Record<string, string>) =>
    Object.entries(items).map(([key, value]) => key + "=" + value).join("\n");
  return {
    name: machine.name,
    image_url: machine.imageUrl,
    source_type: machine.source_type,
    os_type: machine.os_type,
    description: machine.description,
    attachment: machine.attachment ?? "",
    hostname: machine.hostname ?? "",
    command: machine.command ?? "",
    entrypoint: machine.entrypoint ?? "",
    working_dir: machine.working_dir ?? "",
    run_as: machine.run_as ?? "",
    restart_policy: machine.restart_policy,
    privileged: machine.privileged,
    tty: machine.tty,
    stdin_open: machine.stdin_open,
    ports: machine.ports.join("\n"),
    volumes: machine.volumes.join("\n"),
    environment: pairs(machine.environment),
    labels: pairs(machine.labels),
    dns: machine.dns.join("\n"),
    extra_hosts: machine.extra_hosts.join("\n"),
    cap_add: machine.cap_add.join("\n"),
    network_aliases: machine.network_aliases.join("\n"),
    detection_profile: machine.detection_profile ?? "",
    memory_limit: machine.memory_limit,
    cpu_limit: machine.cpu_limit,
  };
}

function MachineForm({
  value,
  onChange,
  onSubmit,
  submitLabel,
  onCancel,
}: {
  value: MachineDraft;
  onChange: (value: MachineDraft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitLabel: string;
  onCancel?: () => void;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-5 border-b border-ink/10 p-4">
      <div className="grid gap-3 lg:grid-cols-[1fr_180px_1fr]">
        <label className="text-sm font-bold text-ink/72">
          Machine name<input
            value={value.name}
            onChange={(event) =>
              onChange({ ...value, name: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder="DVWA target"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Image source<select
            value={value.source_type}
            onChange={(event) =>
              onChange({
                ...value,
                source_type: event.target.value as MachineInput["source_type"],
              })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
          >
            <option value="dockerhub">Docker Hub</option>
            <option value="local">Local image</option>
            <option value="custom">Custom registry URL</option>
          </select>
        </label>
        <label className="text-sm font-bold text-ink/72">
          Image reference<input
            value={value.image_url}
            onChange={(event) =>
              onChange({ ...value, image_url: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder={value.source_type === "dockerhub"
              ? "vulnerables/web-dvwa:latest"
              : value.source_type === "local"
              ? "local/image:tag"
              : "registry.example.local/team/image:tag"}
          />
        </label>
      </div>
      <div className="grid gap-3 lg:grid-cols-[160px_1fr_220px_1fr]">
        <label className="text-sm font-bold text-ink/72">
          OS type<select
            value={value.os_type}
            onChange={(event) =>
              onChange({ ...value, os_type: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
          >
            <option>Linux</option>
            <option>Windows</option>
            <option>Others</option>
          </select>
        </label>
        <label className="text-sm font-bold text-ink/72">
          Description<input
            value={value.description}
            onChange={(event) =>
              onChange({ ...value, description: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder="Approved vulnerable service for web exploitation labs"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Detection profile<input
            value={value.detection_profile}
            onChange={(event) =>
              onChange({ ...value, detection_profile: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder="Imported automatically for repository machines"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Attachment path<input
            value={value.attachment}
            onChange={(event) =>
              onChange({ ...value, attachment: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder="machines/example/wordlist.txt"
          />
        </label>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <label className="text-sm font-bold text-ink/72">
          Memory limit<input
            value={value.memory_limit}
            onChange={(event) =>
              onChange({ ...value, memory_limit: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm"
            placeholder="512m"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          CPU limit<input
            type="number"
            min={0.1}
            max={16}
            step={0.1}
            value={value.cpu_limit}
            onChange={(event) =>
              onChange({ ...value, cpu_limit: Number(event.target.value) })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm"
          />
        </label>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <label className="text-sm font-bold text-ink/72">
          Hostname<input
            value={value.hostname}
            onChange={(event) =>
              onChange({ ...value, hostname: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Working directory<input
            value={value.working_dir}
            onChange={(event) =>
              onChange({ ...value, working_dir: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder="/app"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Run as user<input
            value={value.run_as}
            onChange={(event) =>
              onChange({ ...value, run_as: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
            placeholder="1000:1000"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Command<input
            value={value.command}
            onChange={(event) =>
              onChange({ ...value, command: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Entrypoint<input
            value={value.entrypoint}
            onChange={(event) =>
              onChange({ ...value, entrypoint: event.target.value })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
          />
        </label>
        <label className="text-sm font-bold text-ink/72">
          Restart policy<select
            value={value.restart_policy}
            onChange={(event) =>
              onChange({
                ...value,
                restart_policy: event.target
                  .value as MachineInput["restart_policy"],
              })}
            className="mt-2 min-h-10 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
          >
            <option value="unless-stopped">unless-stopped</option>
            <option value="no">no</option>
            <option value="always">always</option>
            <option value="on-failure">on-failure</option>
          </select>
        </label>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {[
          ["Ports", "ports", "8080:80"],
          ["Volumes", "volumes", "./data:/data:ro"],
          ["Environment", "environment", "FLAG=mayajal{...}"],
          ["Labels", "labels", "mayajal.role=target"],
          ["DNS servers", "dns", "1.1.1.1"],
          ["Extra hosts", "extra_hosts", "host.docker.internal:host-gateway"],
          ["Capabilities", "cap_add", "NET_ADMIN"],
          ["Network aliases", "network_aliases", "target"],
        ].map(([label, key, placeholder]) => (
          <label key={key} className="text-sm font-bold text-ink/72">
            {label}
            <textarea
              value={value[key as keyof MachineDraft] as string}
              onChange={(event) =>
                onChange({ ...value, [key]: event.target.value })}
              className="mt-2 min-h-24 w-full resize-y rounded-md border border-ink/15 px-3 py-2 text-sm outline-none focus:border-fern"
              placeholder={placeholder + "\nOne per line"}
            />
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink/10 pt-4">
        <div className="flex flex-wrap gap-4">
          <label className="inline-flex min-h-10 items-center gap-2 text-sm font-bold text-ink/65">
            <input
              type="checkbox"
              checked={value.tty}
              onChange={(event) =>
                onChange({ ...value, tty: event.target.checked })}
              className="h-4 w-4 accent-[#2f6f5f]"
            />TTY
          </label>
          <label className="inline-flex min-h-10 items-center gap-2 text-sm font-bold text-ink/65">
            <input
              type="checkbox"
              checked={value.stdin_open}
              onChange={(event) =>
                onChange({ ...value, stdin_open: event.target.checked })}
              className="h-4 w-4 accent-[#2f6f5f]"
            />Open stdin
          </label>
          <label className="inline-flex min-h-10 items-center gap-2 text-sm font-bold text-ink/65">
            <input
              type="checkbox"
              checked={value.privileged}
              onChange={(event) =>
                onChange({ ...value, privileged: event.target.checked })}
              className="h-4 w-4 accent-[#2f6f5f]"
            />Privileged
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          {onCancel
            ? (
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-sm font-bold text-ink/65 hover:border-fern/50"
              >
                <X size={16} />Cancel
              </button>
            )
            : null}
          <button
            disabled={!value.name.trim() || !value.image_url.trim()}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-canopy px-3 text-sm font-bold text-white disabled:opacity-50"
          >
            <Plus size={16} />
            {submitLabel}
          </button>
        </div>
      </div>
    </form>
  );
}

function AdminPortal({ apiUrl, view }: { apiUrl: string; view: string }) {
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [labs, setLabs] = useState<ApiLab[]>([]);
  const [machines, setMachines] = useState<ApiMachine[]>([]);
  const [users, setUsers] = useState<AdminDashboard["users"]>([]);
  const [settings, setSettings] = useState<AdminDashboard["settings"]>([]);
  const [notice, setNotice] = useState("");
  const [processLog, setProcessLog] = useState("");
  const [machineDraft, setMachineDraft] = useState<MachineDraft>(
    emptyMachineDraft,
  );
  const [editingMachineId, setEditingMachineId] = useState<string | null>(null);
  const [githubImport, setGitHubImport] = useState<GitHubMachineImportInput>({
    repository_url: "",
    ref: "main",
    machine_path: "",
  });
  const [githubFolders, setGitHubFolders] = useState<GitHubMachineFolder[]>([]);
  const [inspecting, setInspecting] = useState(false);
  const [importing, setImporting] = useState(false);
  useEffect(() => {
    getAdminDashboard(apiUrl).then((dashboard) => {
      setData(dashboard);
      setLabs(dashboard.labs);
      setMachines(dashboard.machines);
      setUsers(dashboard.users);
      setSettings(dashboard.settings);
    }).catch((error) =>
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to load platform controls.",
      )
    );
  }, [apiUrl]);
  async function saveMachine(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const payload = machinePayload(machineDraft);
      const machine = editingMachineId
        ? await updateAdminMachine(apiUrl, editingMachineId, payload)
        : await createAdminMachine(apiUrl, payload);
      setMachines((items) =>
        editingMachineId
          ? items.map((item) => item.id === machine.id ? machine : item)
          : [machine, ...items]
      );
      setMachineDraft(emptyMachineDraft);
      setEditingMachineId(null);
      setNotice(
        machine.name +
          (editingMachineId ? " has been updated." : " has been approved."),
      );
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Enter a valid machine definition.",
      );
    }
  }
  async function importMachine(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setImporting(true);
    setNotice("Downloading and validating the GitHub machine...");
    try {
      const machine = await importGitHubMachine(apiUrl, {
        repository_url: githubImport.repository_url.trim(),
        ref: githubImport.ref.trim(),
        machine_path: githubImport.machine_path.trim(),
      });
      setMachines((items) => [machine, ...items]);
      setGitHubImport({ repository_url: "", ref: "main", machine_path: "" });
      setNotice(
        machine.name +
          " was imported and approved with its detections and attachments.",
      );
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to import the GitHub machine.",
      );
    } finally {
      setImporting(false);
    }
  }
  async function inspectRepository() {
    setInspecting(true);
    setGitHubFolders([]);
    setGitHubImport((value) => ({ ...value, machine_path: "" }));
    setNotice("Inspecting the repository for machine folders...");
    try {
      const result = await discoverGitHubMachines(apiUrl, {
        repository_url: githubImport.repository_url.trim(),
        ref: githubImport.ref.trim(),
      });
      setGitHubFolders(result.machines);
      setGitHubImport((value) => ({
        ...value,
        machine_path: result.machines[0]?.path ?? "",
      }));
      setNotice(
        "Found " + result.machines.length + " importable machine" +
          (result.machines.length === 1 ? "." : "s. Choose one and import it."),
      );
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to inspect the GitHub repository.",
      );
    } finally {
      setInspecting(false);
    }
  }
  function editMachine(machine: ApiMachine) {
    setEditingMachineId(machine.id);
    setMachineDraft(machineDraftFrom(machine));
    setNotice("");
  }
  function cancelMachineEdit() {
    setEditingMachineId(null);
    setMachineDraft(emptyMachineDraft);
  }
  async function refreshMachine(machine: ApiMachine) {
    if (
      !window.confirm(
        "Refresh " + machine.name + " from " + machine.repository_ref + "?",
      )
    ) return;
    setNotice("Refreshing " + machine.name + "...");
    try {
      const refreshed = await refreshGitHubMachine(apiUrl, machine.id);
      setMachines((items) =>
        items.map((item) => item.id === refreshed.id ? refreshed : item)
      );
      setNotice(refreshed.message);
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to refresh the machine.",
      );
    }
  }
  async function updateRole(id: string, role: "student" | "teacher" | "admin") {
    try {
      const result = await changeUserRole(apiUrl, id, role);
      setUsers((items) =>
        items.map((user) => user.id === id ? { ...user, role } : user)
      );
      setNotice(result.message);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to update access.",
      );
    }
  }
  async function toggleSetting(id: string, enabled: boolean) {
    try {
      const result = await changeSetting(apiUrl, id, enabled);
      setSettings((items) =>
        items.map((setting) =>
          setting.id === id ? { ...setting, enabled } : setting
        )
      );
      setNotice(result.message);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to update setting.",
      );
    }
  }
  async function startManagedLab(lab: ApiLab) {
    setProcessLog("");
    setNotice("Starting " + lab.name + "...");
    try {
      await startLabStream(
        apiUrl,
        lab.id,
        (chunk) => setProcessLog((value) => value + chunk),
      );
      setLabs((items) =>
        items.map((item) =>
          item.id === lab.id
            ? {
              ...item,
              status: "running",
              next_step: "Lab containers are running.",
            }
            : item
        )
      );
      setNotice(lab.name + " is running.");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to start the lab.",
      );
    }
  }
  async function stopManagedLab(lab: ApiLab) {
    setProcessLog("");
    setNotice("Stopping " + lab.name + "...");
    try {
      await stopLabStream(
        apiUrl,
        lab.id,
        (chunk) => setProcessLog((value) => value + chunk),
      );
      setLabs((items) =>
        items.map((item) =>
          item.id === lab.id
            ? {
              ...item,
              status: "ready",
              next_step: "Start the lab when you are ready",
            }
            : item
        )
      );
      setNotice(lab.name + " has been stopped.");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to stop the lab.",
      );
    }
  }
  async function downloadManagedVpn(lab: ApiLab) {
    try {
      const result = await getLabVpn(apiUrl, lab.id);
      downloadConfig(result.wireguard_filename, result.wireguard_config);
      setNotice("Downloaded " + result.wireguard_filename + ".");
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to download the VPN config.",
      );
    }
  }
  async function loadManagedReport(lab: ApiLab, reportType: ReportType) {
    try {
      const latest = latestSession(await listLabSessions(apiUrl, lab.id));
      if (!latest) {
        setNotice("No sessions are available for " + lab.name + ".");
        return;
      }
      const [report, pdfDocument] = await Promise.all([
        getAttackReport(apiUrl, latest.id),
        downloadAttackReport(apiUrl, latest.id, reportType),
      ]);
      setProcessLog(formatAttackReport(report));
      downloadBlob(pdfDocument.filename, pdfDocument.blob);
      setNotice("Downloaded " + pdfDocument.filename + ".");
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to generate the attack-chain PDF report.",
      );
    }
  }
  if (!data) {
    return (
      <p className="rounded-lg border border-ink/10 bg-white p-8 text-center text-sm font-semibold text-ink/58">
        Loading platform controls...
      </p>
    );
  }
  if (view === "Machine fleet") {
    return (
      <div className="space-y-5">
        <Notice text={notice} />
        <Panel eyebrow="Repository import" title="Import a machine from GitHub">
          <form onSubmit={importMachine} className="space-y-4 p-4">
            <p className="text-sm leading-6 text-ink/58">
              Enter a public GitHub repository and ref, then let Mayajal find
              every folder containing <strong>machine.json</strong> and{" "}
              <strong>Dockerfile</strong>. Choose one machine to validate and
              import.
            </p>
            <div className="grid gap-3 lg:grid-cols-[minmax(280px,1.5fr)_minmax(130px,0.5fr)_auto] lg:items-end">
              <label className="text-sm font-bold text-ink/72">
                Repository URL<input
                  type="url"
                  required
                  value={githubImport.repository_url}
                  onChange={(event) => {
                    setGitHubImport({
                      ...githubImport,
                      repository_url: event.target.value,
                      machine_path: "",
                    });
                    setGitHubFolders([]);
                  }}
                  className="mt-2 min-h-11 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
                  placeholder="https://github.com/owner/repository"
                />
              </label>
              <label className="text-sm font-bold text-ink/72">
                Git ref<input
                  required
                  value={githubImport.ref}
                  onChange={(event) => {
                    setGitHubImport({
                      ...githubImport,
                      ref: event.target.value,
                      machine_path: "",
                    });
                    setGitHubFolders([]);
                  }}
                  className="mt-2 min-h-11 w-full rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern"
                  placeholder="main"
                />
              </label>
              <button
                type="button"
                onClick={inspectRepository}
                disabled={inspecting || !githubImport.repository_url.trim() ||
                  !githubImport.ref.trim()}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-fern/30 px-4 text-sm font-bold text-fern hover:bg-mint/10 disabled:opacity-50"
              >
                {inspecting
                  ? <LoaderCircle size={16} className="animate-spin" />
                  : <Download size={16} />}
                {inspecting ? "Finding machines" : "Find machines"}
              </button>
            </div>
            {githubFolders.length
              ? (
                <label className="block text-sm font-bold text-ink/72">
                  Machine to import<select
                    required
                    value={githubImport.machine_path}
                    onChange={(event) =>
                      setGitHubImport({
                        ...githubImport,
                        machine_path: event.target.value,
                      })}
                    className="mt-2 min-h-12 w-full rounded-md border border-ink/15 bg-white px-3 text-sm outline-none focus:border-fern"
                  >
                    {githubFolders.map((folder) => (
                      <option key={folder.path} value={folder.path}>
                        {folder.name} — {folder.os_type} — {folder.path}
                      </option>
                    ))}
                  </select>
                  {githubImport.machine_path
                    ? (
                      <span className="mt-2 block text-xs font-medium leading-5 text-ink/50">
                        {githubFolders.find((folder) =>
                          folder.path === githubImport.machine_path
                        )?.description}
                      </span>
                    )
                    : null}
                </label>
              )
              : (
                <p className="rounded-md bg-cloud px-3 py-3 text-sm font-semibold text-ink/54">
                  No repository inspected yet. Select “Find machines” to
                  populate the machine-folder list.
                </p>
              )}
            <div className="flex justify-end">
              <button
                disabled={importing || !githubImport.machine_path}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-canopy px-4 text-sm font-bold text-white disabled:opacity-50"
              >
                {importing
                  ? <LoaderCircle size={16} className="animate-spin" />
                  : <Plus size={16} />}
                {importing
                  ? "Importing and validating"
                  : "Import selected machine"}
              </button>
            </div>
          </form>
        </Panel>
        <Panel
          eyebrow="Machine fleet"
          title={editingMachineId
            ? "Edit machine image"
            : "Approve a machine image"}
        >
          <MachineForm
            value={machineDraft}
            onChange={setMachineDraft}
            onSubmit={saveMachine}
            submitLabel={editingMachineId ? "Save machine" : "Add machine"}
            onCancel={editingMachineId ? cancelMachineEdit : undefined}
          />
          <div className="grid divide-y divide-ink/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
            {machines.map((machine) => (
              <MachineCard
                key={machine.id}
                machine={machine}
                onEdit={editMachine}
                onRefresh={refreshMachine}
              />
            ))}
          </div>
        </Panel>
      </div>
    );
  }
  if (view === "Access control") {
    return (
      <div>
        <Notice text={notice} />
        <Panel eyebrow="Users and roles" title="Account directory">
          <div className="divide-y divide-ink/10">
            {users.map((user) => (
              <div
                key={user.id}
                className="grid gap-3 p-4 sm:grid-cols-[1fr_150px_auto] sm:items-center"
              >
                <div>
                  <p className="text-sm font-black text-ink">{user.name}</p>
                  <p className="mt-1 text-xs text-ink/54">{user.username}</p>
                </div>
                <select
                  value={user.role}
                  onChange={(event) =>
                    updateRole(
                      user.id,
                      event.target.value as "student" | "teacher" | "admin",
                    )}
                  className="min-h-10 rounded-md border border-ink/15 px-3 text-sm font-semibold outline-none focus:border-fern"
                >
                  <option value="student">Student</option>
                  <option value="teacher">Teacher</option>
                  <option value="admin">Administrator</option>
                </select>
                <span className="text-xs font-bold text-fern">
                  {user.status}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    );
  }
  if (view === "System settings") {
    return (
      <div>
        <Notice text={notice} />
        <Panel eyebrow="System settings" title="Platform policies">
          <div className="divide-y divide-ink/10">
            {settings.map((setting) => (
              <label
                key={setting.id}
                className="flex min-h-16 cursor-pointer items-center justify-between gap-4 p-4"
              >
                <span>
                  <span className="block text-sm font-black text-ink">
                    {setting.label}
                  </span>
                  <span className="mt-1 block text-xs text-ink/54">
                    Applies across the Mayajal environment
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={setting.enabled}
                  onChange={(event) =>
                    toggleSetting(setting.id, event.target.checked)}
                  className="h-5 w-5 accent-[#2f6f5f]"
                />
              </label>
            ))}
          </div>
        </Panel>
      </div>
    );
  }
  const logPanel = processLog
    ? (
      <Panel eyebrow="Container output" title="Docker Compose stream">
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap bg-ink p-4 text-xs leading-5 text-white">{processLog}</pre>
      </Panel>
    )
    : null;
  if (view === "Lab catalogue") {
    return (
      <div className="space-y-5">
        <Notice text={notice} />
        {logPanel}
        <Panel eyebrow="Lab catalogue" title="Platform lab inventory">
          <LabList
            labs={labs}
            machines={machines}
            onStart={startManagedLab}
            onStop={stopManagedLab}
            onDownloadVpn={downloadManagedVpn}
            onReport={loadManagedReport}
          />
        </Panel>
      </div>
    );
  }
  return (
    <div>
      <Notice text={notice} />
      {logPanel ? <div className="mb-5">{logPanel}</div> : null}
      <div className="grid gap-4 md:grid-cols-4">
        {[
          [
            "Running sessions",
            String(data.metrics?.running_sessions ?? 0),
            Activity,
          ],
          [
            "Students",
            String(
              data.metrics?.students ??
                users.filter((user) => user.role === "student").length,
            ),
            Users,
          ],
          ["Labs", String(data.metrics?.labs ?? labs.length), Layers3],
          ["Approved images", String(machines.length), ServerCog],
        ].map(([label, value, Icon]) => {
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
            </div>
          );
        })}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Panel eyebrow="Running sessions" title="Student lab activity">
          <div className="divide-y divide-ink/10">
            {data.running_sessions.length
              ? data.running_sessions.map((session) => (
                <div
                  key={session.id}
                  className="grid gap-2 p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-center"
                >
                  <div>
                    <p className="text-sm font-black text-ink">
                      {session.student}
                    </p>
                    <p className="mt-1 text-xs text-ink/54">{session.lab}</p>
                  </div>
                  <p className="text-xs font-semibold text-ink/54">
                    {new Date(session.started_at).toLocaleString()}
                  </p>
                  <span className="rounded-full bg-mint/20 px-2.5 py-1 text-xs font-bold text-fern">
                    {session.status}
                  </span>
                </div>
              ))
              : (
                <p className="p-6 text-center text-sm text-ink/54">
                  No running sessions.
                </p>
              )}
          </div>
        </Panel>
        <Panel eyebrow="System health" title="Service status">
          <div className="divide-y divide-ink/10">
            {data.health.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between p-4"
              >
                <span className="text-sm font-black text-ink">{item.name}</span>
                <span className="inline-flex items-center gap-2 text-sm font-bold text-fern">
                  <Check size={16} />
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

export default function ManagementPortal(
  { apiUrl, role, view }: {
    apiUrl: string;
    role: "teacher" | "admin";
    view: string;
  },
) {
  return role === "teacher"
    ? <TeacherPortal apiUrl={apiUrl} view={view} />
    : <AdminPortal apiUrl={apiUrl} view={view} />;
}
