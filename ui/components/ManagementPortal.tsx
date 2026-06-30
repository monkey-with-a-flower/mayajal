"use client";

import { FormEvent, useEffect, useState } from "react";
import clsx from "clsx";
import { Activity, Check, ClipboardCheck, Edit3, Layers3, Plus, Save, ServerCog, Trash2, Users, X } from "lucide-react";
import {
  changeSetting,
  changeUserRole,
  completeReview,
  createAdminMachine,
  createTeacherLab,
  deleteTeacherLab,
  getAdminDashboard,
  getTeacherDashboard,
  updateTeacherLab,
  type AdminDashboard,
  type ApiLab,
  type ApiMachine,
  type TeacherDashboard,
  type TeacherLabInput,
} from "@/lib/api";

function Panel({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <section className="rounded-lg border border-ink/10 bg-white shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 p-4"><div><p className="text-xs font-bold uppercase text-ink/44">{eyebrow}</p><h2 className="mt-1 text-xl font-black text-ink">{title}</h2></div>{action}</div>{children}</section>;
}

function Button({ children, icon: Icon, onClick, disabled }: { children: React.ReactNode; icon: typeof Plus; onClick?: () => void; disabled?: boolean }) {
  return <button type="button" onClick={onClick} disabled={disabled} className={clsx("inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-3 text-sm font-bold", disabled ? "cursor-not-allowed bg-ink/8 text-ink/35" : "bg-canopy text-white hover:bg-fern")}><Icon size={16} />{children}</button>;
}

function Notice({ text }: { text: string }) { return text ? <p className="mb-5 rounded-lg border border-fern/25 bg-mint/15 px-4 py-3 text-sm font-bold text-fern">{text}</p> : null; }

type LabDraft = {
  name: string;
  description: string;
  machine_ids: string[];
  tasks: string[];
  status: ApiLab["status"];
};

const emptyLabDraft: LabDraft = { name: "", description: "", machine_ids: [], tasks: [""], status: "ready" };

function LabForm({
  machines,
  value,
  onChange,
  onSubmit,
  submitLabel,
  saving,
}: {
  machines: ApiMachine[];
  value: LabDraft;
  onChange: (value: LabDraft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitLabel: string;
  saving?: boolean;
}) {
  function toggleMachine(id: string) {
    onChange({ ...value, machine_ids: value.machine_ids.includes(id) ? value.machine_ids.filter((item) => item !== id) : [...value.machine_ids, id] });
  }

  function updateTask(index: number, task: string) {
    onChange({ ...value, tasks: value.tasks.map((item, itemIndex) => itemIndex === index ? task : item) });
  }

  function removeTask(index: number) {
    onChange({ ...value, tasks: value.tasks.filter((_, itemIndex) => itemIndex !== index) });
  }

  return <form onSubmit={onSubmit} className="space-y-5 p-4">
    <div className="grid gap-4 lg:grid-cols-[minmax(180px,0.75fr)_minmax(260px,1.25fr)]">
      <label className="text-sm font-bold text-ink/72">Lab name<input value={value.name} onChange={(event) => onChange({ ...value, name: event.target.value })} className="mt-2 min-h-11 w-full rounded-md border border-ink/15 px-3 text-sm font-semibold text-ink outline-none focus:border-fern" placeholder="e.g. Suspicious payroll portal" /></label>
      <label className="text-sm font-bold text-ink/72">Scenario description<textarea value={value.description} onChange={(event) => onChange({ ...value, description: event.target.value })} className="mt-2 min-h-28 w-full resize-y rounded-md border border-ink/15 px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-fern" placeholder="Tell the story: the company, the environment, what machines are involved, and what students need to investigate." /></label>
    </div>
    <div>
      <p className="text-sm font-black text-ink">Machines in this lab</p>
      <div className="mt-3 grid gap-3 md:grid-cols-3">{machines.map((machine) => {
        const selected = value.machine_ids.includes(machine.id);
        return <button key={machine.id} type="button" onClick={() => toggleMachine(machine.id)} className={clsx("rounded-md border p-3 text-left transition", selected ? "border-fern bg-mint/10" : "border-ink/10 hover:border-fern/50")}><span className="flex items-center justify-between gap-2"><ServerCog size={18} className="text-canopy" /><span className={clsx("grid h-5 w-5 place-items-center rounded-full", selected ? "bg-fern text-white" : "bg-ink/10 text-transparent")}><Check size={13} /></span></span><p className="mt-3 text-sm font-black text-ink">{machine.name}</p><p className="mt-1 text-xs text-ink/50">{machine.os_type}</p></button>;
      })}</div>
    </div>
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-black text-ink">Student flags and questions</p>
        <button type="button" onClick={() => onChange({ ...value, tasks: [...value.tasks, ""] })} className="inline-flex min-h-9 items-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50"><Plus size={15} />Add question</button>
      </div>
      <div className="mt-3 space-y-2">{value.tasks.map((task, index) => <div key={index} className="grid gap-2 sm:grid-cols-[auto_1fr_auto] sm:items-center"><span className="text-xs font-bold text-ink/45">#{index + 1}</span><input value={task} onChange={(event) => updateTask(index, event.target.value)} className="min-h-10 rounded-md border border-ink/15 px-3 text-sm outline-none focus:border-fern" placeholder="e.g. What service exposes the payroll login?" />{value.tasks.length > 1 ? <button type="button" onClick={() => removeTask(index)} className="inline-flex min-h-10 items-center justify-center rounded-md border border-clay/25 px-3 text-clay hover:bg-clay/10"><Trash2 size={16} /></button> : null}</div>)}</div>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink/10 pt-4">
      <label className="flex min-h-10 items-center gap-2 text-sm font-bold text-ink/65"><input type="checkbox" checked={value.status !== "locked"} onChange={(event) => onChange({ ...value, status: event.target.checked ? "ready" : "locked" })} className="h-4 w-4 accent-[#2f6f5f]" /> Publish for assigned students</label>
      <button disabled={saving || !value.name.trim() || value.description.trim().length < 10 || !value.machine_ids.length} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-canopy px-3 text-sm font-bold text-white disabled:opacity-50"><Save size={16} />{saving ? "Saving" : submitLabel}</button>
    </div>
  </form>;
}

function LabList({
  labs,
  machines,
  editable = false,
  onSave,
  onDelete,
}: {
  labs: ApiLab[];
  machines: ApiMachine[];
  editable?: boolean;
  onSave?: (lab: ApiLab) => Promise<void>;
  onDelete?: (lab: ApiLab) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<LabDraft>(emptyLabDraft);
  const [busyId, setBusyId] = useState<string | null>(null);

  function beginEdit(lab: ApiLab) {
    setEditingId(lab.id);
    setDraft({ name: lab.name, description: lab.description, machine_ids: lab.machine_ids, tasks: lab.tasks.length ? lab.tasks : [""], status: lab.status });
  }

  async function save(lab: ApiLab) {
    if (!onSave || !draft.name.trim() || draft.description.trim().length < 10 || !draft.machine_ids.length) return;
    setBusyId(lab.id);
    try {
      await onSave({ ...lab, name: draft.name.trim(), description: draft.description.trim(), machine_ids: draft.machine_ids, tasks: draft.tasks.map((task) => task.trim()).filter(Boolean), status: draft.status });
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

  return <div className="divide-y divide-ink/10">{labs.length ? labs.map((lab) => {
    const isEditing = editingId === lab.id;
    const disabled = busyId === lab.id;
    return <div key={lab.id} className="p-4">
      {isEditing ? <div className="space-y-3">
        <LabForm machines={machines} value={draft} onChange={setDraft} submitLabel="Save lab" saving={disabled} onSubmit={(event) => { event.preventDefault(); save(lab); }} />
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" onClick={() => setEditingId(null)} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-sm font-bold text-ink/65 hover:border-fern/50"><X size={16} />Cancel</button>
        </div>
      </div> : <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-black text-ink">{lab.name}</p>
          <p className="mt-1 text-xs text-ink/54">{lab.description || "No description yet."}</p>
          <p className="mt-2 text-xs font-semibold text-ink/42">{lab.level} - {lab.runtime} - {lab.owner} - {lab.machine_ids.length} machines - {lab.tasks.length} questions</p>
          {lab.tasks.length ? <ul className="mt-3 grid gap-1 text-xs text-ink/55">{lab.tasks.slice(0, 3).map((task) => <li key={task} className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-fern" />{task}</li>)}</ul> : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className={clsx("rounded-full px-2.5 py-1 text-xs font-bold", lab.status === "locked" ? "bg-cloud text-ink/55" : "bg-mint/20 text-fern")}>{lab.status === "locked" ? "Draft" : "Published"}</span>
          {editable ? <>
            <button type="button" onClick={() => beginEdit(lab)} disabled={disabled} className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-ink/12 px-3 text-xs font-bold text-ink/65 hover:border-fern/50 disabled:opacity-50"><Edit3 size={15} />Edit</button>
            <button type="button" onClick={() => remove(lab)} disabled={disabled} className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-clay/25 px-3 text-xs font-bold text-clay hover:bg-clay/10 disabled:opacity-50"><Trash2 size={15} />Remove</button>
          </> : null}
        </div>
      </div>}
    </div>;
  }) : <p className="p-6 text-center text-sm font-semibold text-ink/54">No labs yet.</p>}</div>;
}

function TeacherPortal({ apiUrl, view }: { apiUrl: string; view: string }) {
  const [data, setData] = useState<TeacherDashboard | null>(null); const [labs, setLabs] = useState<ApiLab[]>([]); const [reviews, setReviews] = useState<TeacherDashboard["reviews"]>([]); const [notice, setNotice] = useState(""); const [newLab, setNewLab] = useState<LabDraft>(emptyLabDraft); const [saving, setSaving] = useState(false);
  useEffect(() => { getTeacherDashboard(apiUrl).then((dashboard) => { setData(dashboard); setLabs(dashboard.labs); setReviews(dashboard.reviews); setNewLab((draft) => ({ ...draft, machine_ids: draft.machine_ids.length ? draft.machine_ids : dashboard.machines.slice(0, 2).map((machine) => machine.id) })); }).catch((error) => setNotice(error instanceof Error ? error.message : "Unable to load teaching workspace.")); }, [apiUrl]);
  async function createLab(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!newLab.name.trim() || newLab.description.trim().length < 10 || !newLab.machine_ids.length) { setNotice("Add a lab name, scenario description, and at least one machine."); return; } setSaving(true); try { const payload: TeacherLabInput = { name: newLab.name.trim(), description: newLab.description.trim(), machine_ids: newLab.machine_ids, tasks: newLab.tasks.map((task) => task.trim()).filter(Boolean), publish: newLab.status !== "locked" }; const lab = await createTeacherLab(apiUrl, payload); setLabs((items) => [lab, ...items]); setNewLab({ ...emptyLabDraft, machine_ids: data?.machines.slice(0, 2).map((machine) => machine.id) ?? [] }); setNotice(lab.name + " has been created."); } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to create the lab."); } finally { setSaving(false); } }
  async function saveLab(lab: ApiLab) { try { const updated = await updateTeacherLab(apiUrl, lab); setLabs((items) => items.map((item) => item.id === updated.id ? updated : item)); setNotice(updated.name + " has been updated."); } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to update the lab."); throw error; } }
  async function removeLab(lab: ApiLab) { try { const result = await deleteTeacherLab(apiUrl, lab.id); setLabs((items) => items.filter((item) => item.id !== lab.id)); setReviews((items) => items.filter((item) => item.lab !== lab.name)); setNotice(result.message); } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to remove the lab."); throw error; } }
  async function review(id: string) { try { const result = await completeReview(apiUrl, id); setReviews((items) => items.filter((item) => item.id !== id)); setNotice(result.message); } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to record feedback."); } }
  if (!data) return <p className="rounded-lg border border-ink/10 bg-white p-8 text-center text-sm font-semibold text-ink/58">Loading teaching workspace...</p>;
  const library = <Panel eyebrow="Machine library" title="Approved environments"><div className="grid divide-y divide-ink/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0">{data.machines.map((machine) => <MachineCard key={machine.id} machine={machine} />)}</div></Panel>;
  if (view === "Class labs") return <div><Notice text={notice} /><Panel eyebrow="Class labs" title="Author and publish labs"><LabForm machines={data.machines} value={newLab} onChange={setNewLab} onSubmit={createLab} submitLabel="Create lab" saving={saving} /><LabList labs={labs} machines={data.machines} editable onSave={saveLab} onDelete={removeLab} /></Panel></div>;
  if (view === "Students") return <div><Notice text={notice} /><div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]"><Panel eyebrow="Learners" title="Class progress"><div className="divide-y divide-ink/10">{data.students.map((student) => <div key={student.id} className="p-4"><div className="flex justify-between gap-3"><div><p className="text-sm font-black text-ink">{student.name}</p><p className="mt-1 text-xs text-ink/54">{student.cohort} - {student.active_labs} active labs</p></div><p className="text-sm font-bold text-fern">{student.progress}%</p></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-cloud"><div className="h-full bg-fern" style={{ width: student.progress + "%" }} /></div></div>)}</div></Panel><Panel eyebrow="Review queue" title="Student activity"><div className="divide-y divide-ink/10">{reviews.length ? reviews.map((item) => <div key={item.id} className="p-4"><p className="text-sm font-black text-ink">{item.student}</p><p className="mt-1 text-xs text-ink/54">{item.lab}</p><div className="mt-3 flex items-center justify-between gap-3"><span className="text-xs font-bold text-fern">{item.state}</span><Button icon={ClipboardCheck} onClick={() => review(item.id)}>Review</Button></div></div>) : <p className="p-6 text-center text-sm text-ink/54">Review queue is clear.</p>}</div></Panel></div></div>;
  if (view === "Machine library") return library;
  return <div><Notice text={notice} /><div className="grid gap-4 md:grid-cols-3">{[["Published labs", String(labs.filter((lab) => lab.status !== "locked").length), Layers3], ["Active students", String(data.students.length), Users], ["Reviews due", String(reviews.length), ClipboardCheck]].map(([label, value, Icon]) => { const Metric = Icon as typeof Activity; return <div key={label as string} className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm"><div className="flex justify-between"><div><p className="text-sm font-semibold text-ink/55">{label as string}</p><p className="mt-2 text-3xl font-black text-ink">{value as string}</p></div><span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy"><Metric size={20} /></span></div></div>; })}</div><div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]"><Panel eyebrow="Class labs" title="Your catalogue"><LabList labs={labs.slice(0, 3)} machines={data.machines} editable onSave={saveLab} onDelete={removeLab} /></Panel><Panel eyebrow="Review queue" title="Needs attention"><div className="divide-y divide-ink/10">{reviews.slice(0, 3).map((item) => <div key={item.id} className="p-4"><p className="text-sm font-black text-ink">{item.student}</p><p className="mt-1 text-xs text-ink/54">{item.lab}</p></div>)}</div></Panel></div></div>;
}

function MachineCard({ machine }: { machine: ApiMachine }) { return <div className="p-4"><div className="flex items-center justify-between"><span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy"><ServerCog size={19} /></span><span className="rounded-md bg-cloud px-2 py-1 text-xs font-bold text-ink/55">{machine.os_type}</span></div><p className="mt-4 text-sm font-black text-ink">{machine.name}</p><p className="mt-1 text-xs leading-5 text-ink/54">{machine.description}</p><p className="mt-3 truncate text-xs font-semibold text-fern">{machine.imageUrl}</p></div>; }

function AdminPortal({ apiUrl, view }: { apiUrl: string; view: string }) {
  const [data, setData] = useState<AdminDashboard | null>(null); const [machines, setMachines] = useState<ApiMachine[]>([]); const [users, setUsers] = useState<AdminDashboard["users"]>([]); const [settings, setSettings] = useState<AdminDashboard["settings"]>([]); const [notice, setNotice] = useState(""); const [name, setName] = useState(""); const [osType, setOsType] = useState("Linux");
  useEffect(() => { getAdminDashboard(apiUrl).then((dashboard) => { setData(dashboard); setMachines(dashboard.machines); setUsers(dashboard.users); setSettings(dashboard.settings); }).catch((error) => setNotice(error instanceof Error ? error.message : "Unable to load platform controls.")); }, [apiUrl]);
  async function addMachine(event: FormEvent<HTMLFormElement>) { event.preventDefault(); try { const machine = await createAdminMachine(apiUrl, name, osType); setMachines((items) => [machine, ...items]); setName(""); setNotice(machine.name + " has been approved."); } catch (error) { setNotice(error instanceof Error ? error.message : "Enter a machine name."); } }
  async function updateRole(id: string, role: "student" | "teacher" | "admin") { try { const result = await changeUserRole(apiUrl, id, role); setUsers((items) => items.map((user) => user.id === id ? { ...user, role } : user)); setNotice(result.message); } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to update access."); } }
  async function toggleSetting(id: string, enabled: boolean) { try { const result = await changeSetting(apiUrl, id, enabled); setSettings((items) => items.map((setting) => setting.id === id ? { ...setting, enabled } : setting)); setNotice(result.message); } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to update setting."); } }
  if (!data) return <p className="rounded-lg border border-ink/10 bg-white p-8 text-center text-sm font-semibold text-ink/58">Loading platform controls...</p>;
  if (view === "Machine fleet") return <div><Notice text={notice} /><Panel eyebrow="Machine fleet" title="Approve a machine image"><form onSubmit={addMachine} className="grid gap-3 border-b border-ink/10 p-4 sm:grid-cols-[1fr_150px_auto]"><input value={name} onChange={(event) => setName(event.target.value)} className="min-h-10 rounded-md border border-ink/15 px-3 outline-none focus:border-fern" placeholder="Machine name" /><select value={osType} onChange={(event) => setOsType(event.target.value)} className="min-h-10 rounded-md border border-ink/15 px-3 outline-none focus:border-fern"><option>Linux</option><option>Windows</option><option>Others</option></select><button className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-canopy px-3 text-sm font-bold text-white"><Plus size={16} />Add image</button></form><div className="grid divide-y divide-ink/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0">{machines.map((machine) => <MachineCard key={machine.id} machine={machine} />)}</div></Panel></div>;
  if (view === "Access control") return <div><Notice text={notice} /><Panel eyebrow="Users and roles" title="Account directory"><div className="divide-y divide-ink/10">{users.map((user) => <div key={user.id} className="grid gap-3 p-4 sm:grid-cols-[1fr_150px_auto] sm:items-center"><div><p className="text-sm font-black text-ink">{user.name}</p><p className="mt-1 text-xs text-ink/54">{user.username}</p></div><select value={user.role} onChange={(event) => updateRole(user.id, event.target.value as "student" | "teacher" | "admin")} className="min-h-10 rounded-md border border-ink/15 px-3 text-sm font-semibold outline-none focus:border-fern"><option value="student">Student</option><option value="teacher">Teacher</option><option value="admin">Administrator</option></select><span className="text-xs font-bold text-fern">{user.status}</span></div>)}</div></Panel></div>;
  if (view === "System settings") return <div><Notice text={notice} /><Panel eyebrow="System settings" title="Platform policies"><div className="divide-y divide-ink/10">{settings.map((setting) => <label key={setting.id} className="flex min-h-16 cursor-pointer items-center justify-between gap-4 p-4"><span><span className="block text-sm font-black text-ink">{setting.label}</span><span className="mt-1 block text-xs text-ink/54">Applies across the Mayajal environment</span></span><input type="checkbox" checked={setting.enabled} onChange={(event) => toggleSetting(setting.id, event.target.checked)} className="h-5 w-5 accent-[#2f6f5f]" /></label>)}</div></Panel></div>;
  if (view === "Lab catalogue") return <Panel eyebrow="Lab catalogue" title="Platform lab inventory"><LabList labs={data.labs} machines={machines} /></Panel>;
  return <div><Notice text={notice} /><div className="grid gap-4 md:grid-cols-3">{[["Running labs", "18", Activity], ["Approved images", String(machines.length), ServerCog], ["Managed accounts", String(users.length), Users]].map(([label, value, Icon]) => { const Metric = Icon as typeof Activity; return <div key={label as string} className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm"><div className="flex justify-between"><div><p className="text-sm font-semibold text-ink/55">{label as string}</p><p className="mt-2 text-3xl font-black text-ink">{value as string}</p></div><span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy"><Metric size={20} /></span></div></div>; })}</div><div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]"><Panel eyebrow="System health" title="Service status"><div className="divide-y divide-ink/10">{data.health.map((item) => <div key={item.name} className="flex items-center justify-between p-4"><span className="text-sm font-black text-ink">{item.name}</span><span className="inline-flex items-center gap-2 text-sm font-bold text-fern"><Check size={16} />{item.value}</span></div>)}</div></Panel><Panel eyebrow="Access control" title="Role coverage"><div className="space-y-3 p-4">{["Student: assigned labs and personal scenarios", "Teacher: labs, machines, and learner reviews", "Administrator: platform-wide controls"].map((item) => <p key={item} className="rounded-md bg-cloud p-3 text-sm font-semibold text-ink/65">{item}</p>)}</div></Panel></div></div>;
}

export default function ManagementPortal({ apiUrl, role, view }: { apiUrl: string; role: "teacher" | "admin"; view: string }) { return role === "teacher" ? <TeacherPortal apiUrl={apiUrl} view={view} /> : <AdminPortal apiUrl={apiUrl} view={view} />; }
