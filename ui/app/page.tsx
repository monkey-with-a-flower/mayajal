"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import {
  Activity,
  ArrowRight,
  BookOpenCheck,
  Check,
  ChevronRight,
  Circle,
  ClipboardCheck,
  Cpu,
  Gauge,
  KeyRound,
  Layers3,
  LockKeyhole,
  LogOut,
  Network,
  Play,
  Plus,
  Search,
  ServerCog,
  Settings2,
  Shield,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import { accounts, labs, machines, roleProfiles, type Account, type Role } from "@/lib/data";
import StudentPortal from "@/components/StudentPortal";
import ManagementPortal from "@/components/ManagementPortal";
import { signIn } from "@/lib/api";

const roleNavigation: Record<Role, { label: string; icon: typeof ShieldCheck }[]> = {
  student: [
    { label: "My learning", icon: BookOpenCheck },
    { label: "Assigned labs", icon: Play },
    { label: "My scenarios", icon: Layers3 },
    { label: "Machine library", icon: Network },
  ],
  teacher: [
    { label: "Teaching", icon: BookOpenCheck },
    { label: "Class labs", icon: Layers3 },
    { label: "Students", icon: Users },
    { label: "Machine library", icon: Network },
  ],
  admin: [
    { label: "Platform", icon: ShieldCheck },
    { label: "Lab catalogue", icon: BookOpenCheck },
    { label: "Machine fleet", icon: ServerCog },
    { label: "Access control", icon: KeyRound },
    { label: "System settings", icon: Settings2 },
  ],
};

const roleMetrics: Record<Role, { label: string; value: string; detail: string; icon: typeof Activity }[]> = {
  student: [
    { label: "Active labs", value: "2", detail: "1 ready to resume", icon: Play },
    { label: "This week", value: "4.5h", detail: "lab runtime", icon: Activity },
    { label: "Personal scenarios", value: "3", detail: "saved workspaces", icon: Layers3 },
  ],
  teacher: [
    { label: "Published labs", value: "12", detail: "across 4 classes", icon: BookOpenCheck },
    { label: "Active students", value: "86", detail: "this week", icon: Users },
    { label: "Reviews due", value: "9", detail: "awaiting feedback", icon: ClipboardCheck },
  ],
  admin: [
    { label: "Running labs", value: "18", detail: "across all cohorts", icon: Play },
    { label: "Managed users", value: "248", detail: "3 access profiles", icon: Users },
    { label: "Approved images", value: "42", detail: "machine catalogue", icon: ServerCog },
  ],
};

function ActionButton({
  children,
  icon: Icon,
  tone = "primary",
}: {
  children: ReactNode;
  icon: typeof Plus;
  tone?: "primary" | "secondary";
}) {
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-bold transition",
        tone === "primary"
          ? "border-canopy bg-canopy text-white hover:bg-fern"
          : "border-ink/12 bg-white text-ink hover:border-fern/50",
      )}
    >
      <Icon size={16} />
      {children}
    </button>
  );
}

function MetricCard({ metric }: { metric: (typeof roleMetrics)[Role][number] }) {
  const Icon = metric.icon;
  return (
    <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-ink/55">{metric.label}</p>
          <p className="mt-2 text-3xl font-black text-ink">{metric.value}</p>
        </div>
        <span className="grid h-10 w-10 place-items-center rounded-md bg-mint/20 text-canopy">
          <Icon size={20} />
        </span>
      </div>
      <p className="mt-3 text-xs font-bold text-fern">{metric.detail}</p>
    </div>
  );
}

function Panel({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
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

function LabList({ role }: { role: Role }) {
  const visibleLabs = role === "student" ? labs.filter((lab) => lab.status === "Published") : labs;
  const verb = role === "student" ? "Launch" : role === "teacher" ? "Open" : "Manage";

  return (
    <div className="divide-y divide-ink/10">
      {visibleLabs.map((lab) => (
        <article key={lab.title} className="grid gap-4 p-4 sm:grid-cols-[1fr_auto] sm:items-center">
          <div className="flex min-w-0 gap-3">
            <span className={clsx("mt-1 h-12 w-2 shrink-0 rounded-full", lab.accent)} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-black text-ink">{lab.title}</h3>
                <span className="rounded-full bg-cloud px-2.5 py-1 text-xs font-bold text-ink/58">
                  {lab.status}
                </span>
              </div>
              <p className="mt-1 text-sm text-ink/58">
                {lab.level} - {lab.runtime} - {lab.machines.join(", ")}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-canopy/20 px-3 text-sm font-bold text-canopy transition hover:bg-canopy hover:text-white"
          >
            {verb}
            <ChevronRight size={16} />
          </button>
        </article>
      ))}
    </div>
  );
}

function ScenarioBuilder({ teacher = false }: { teacher?: boolean }) {
  return (
    <Panel
      eyebrow={teacher ? "Lab authoring" : "Personal scenario"}
      title={teacher ? "Build a classroom lab" : "Compose a personal scenario"}
      action={<ActionButton icon={Plus}>{teacher ? "New lab" : "Save scenario"}</ActionButton>}
    >
      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_250px]">
        <div className="rounded-lg border border-dashed border-fern/35 bg-cloud p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-black text-ink">Network layout</p>
              <p className="mt-1 text-xs leading-5 text-ink/55">
                Select approved machines and arrange an isolated lab environment.
              </p>
            </div>
            <Layers3 className="text-fern" size={22} />
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              ["Attacker", "Kali Workstation"],
              ["Target", "DVWA"],
              ["Observer", "Suricata Sensor"],
            ].map(([name, machine]) => (
              <div key={name} className="min-h-28 rounded-md border border-ink/10 bg-white p-3 shadow-sm">
                <Cpu size={18} className="text-canopy" />
                <p className="mt-4 text-sm font-black text-ink">{name}</p>
                <p className="mt-1 text-xs text-ink/52">{machine}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-ink/10 p-3">
          <label className="flex items-center gap-2 rounded-md border border-ink/10 px-3 py-2 text-ink/44">
            <Search size={16} />
            <input className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink/35" placeholder="Find machines" />
          </label>
          <div className="mt-3 space-y-2">
            {machines.slice(0, 3).map((machine) => (
              <button key={machine.name} type="button" className="w-full rounded-md border border-ink/10 p-3 text-left hover:border-fern/50">
                <p className="text-sm font-black text-ink">{machine.name}</p>
                <p className="mt-1 truncate text-xs text-ink/48">{machine.os} - {machine.image}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function StudentWorkspace() {
  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <Panel eyebrow="Assigned labs" title="Continue learning" action={<ActionButton icon={Play}>Launch a lab</ActionButton>}>
          <LabList role="student" />
        </Panel>
        <Panel eyebrow="Learning path" title="This week">
          <div className="space-y-4 p-4">
            {[
              ["Web Exploit Basics", "Complete the input validation module", "72%"],
              ["Packet analysis", "Start the traffic capture exercise", "Next"],
              ["Scenario design", "Save one personal lab scenario", "1 of 3"],
            ].map(([title, detail, progress]) => (
              <div key={title} className="rounded-md bg-cloud p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-black text-ink">{title}</p>
                  <span className="text-xs font-bold text-fern">{progress}</span>
                </div>
                <p className="mt-1 text-xs leading-5 text-ink/54">{detail}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <ScenarioBuilder />
    </div>
  );
}

function TeacherWorkspace() {
  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <Panel eyebrow="Class labs" title="Your lab catalogue" action={<ActionButton icon={Plus}>Create lab</ActionButton>}>
          <LabList role="teacher" />
        </Panel>
        <Panel eyebrow="Review queue" title="Student activity" action={<ActionButton icon={ClipboardCheck} tone="secondary">Open queue</ActionButton>}>
          <div className="space-y-3 p-4">
            {[
              ["Amir Hussain", "Windows Privilege Path", "Ready for review"],
              ["Lena Chen", "Web Exploit Basics", "Requested help"],
              ["Noah Williams", "Packet Hunt", "Completed"],
            ].map(([name, lab, state]) => (
              <div key={name} className="flex items-center justify-between gap-3 rounded-md bg-cloud p-3">
                <div>
                  <p className="text-sm font-black text-ink">{name}</p>
                  <p className="mt-1 text-xs text-ink/54">{lab}</p>
                </div>
                <span className="text-right text-xs font-bold text-fern">{state}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <ScenarioBuilder teacher />
    </div>
  );
}

function AdminWorkspace() {
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
      <div className="space-y-6">
        <Panel eyebrow="Platform operations" title="Lab catalogue" action={<ActionButton icon={Plus}>Create lab</ActionButton>}>
          <LabList role="admin" />
        </Panel>
        <Panel eyebrow="Machine fleet" title="Approved machine images" action={<ActionButton icon={Plus}>Add machine</ActionButton>}>
          <div className="grid divide-y divide-ink/10 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
            {machines.map((machine) => (
              <div key={machine.name} className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-black text-ink">{machine.name}</p>
                  <span className="rounded-md bg-cloud px-2 py-1 text-xs font-bold text-ink/58">{machine.os}</span>
                </div>
                <p className="mt-2 truncate text-xs text-ink/48">{machine.image}</p>
                <p className="mt-2 text-xs font-bold text-fern">Approved by {machine.addedBy}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <div className="space-y-6">
        <Panel eyebrow="Access control" title="Account directory" action={<ActionButton icon={Users} tone="secondary">Manage users</ActionButton>}>
          <div className="divide-y divide-ink/10">
            {accounts.map((member) => (
              <div key={member.username} className="flex items-center gap-3 p-4">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-canopy text-sm font-black text-white">{member.initials}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-black text-ink">{member.name}</p>
                  <p className="mt-1 text-xs text-ink/52">{member.username}</p>
                </div>
                <span className="rounded-full bg-mint/20 px-2.5 py-1 text-xs font-bold text-fern">{roleProfiles[member.role].label}</span>
              </div>
            ))}
          </div>
        </Panel>
        <section className="rounded-lg bg-canopy p-5 text-white shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase text-white/58">System health</p>
              <h2 className="mt-1 text-xl font-black">All services operational</h2>
            </div>
            <ShieldCheck size={24} />
          </div>
          <div className="mt-5 space-y-3 text-sm">
            <p className="flex items-center justify-between gap-3"><span className="text-white/70">Lab scheduler</span><span className="font-bold">Healthy</span></p>
            <p className="flex items-center justify-between gap-3"><span className="text-white/70">Machine catalogue</span><span className="font-bold">42 images</span></p>
            <p className="flex items-center justify-between gap-3"><span className="text-white/70">Access policies</span><span className="font-bold">Enforced</span></p>
          </div>
        </section>
      </div>
    </div>
  );
}

function SignIn({ onSignIn }: { onSignIn: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await onSignIn(username, password);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-4 sm:p-8">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-lg border border-ink/10 bg-white shadow-panel lg:grid-cols-[0.9fr_1.1fr]">
        <section className="bg-canopy p-6 text-white sm:p-10">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-lg bg-white text-canopy"><Shield size={23} /></span>
            <div><p className="text-lg font-black">Mayajal</p><p className="text-xs font-semibold text-white/62">Cyber lab workspace</p></div>
          </div>
          <div className="mt-14 max-w-sm">
            <p className="text-sm font-bold text-mint">Secure learning environments</p>
            <h1 className="mt-3 text-4xl font-black leading-tight">Build skills in controlled labs.</h1>
            <p className="mt-4 text-sm leading-6 text-white/70">Launch assigned work, create guided scenarios, and manage each environment through role-based access.</p>
          </div>
        </section>
        <section className="p-6 sm:p-10">
          <p className="text-xs font-bold uppercase text-ink/45">Account access</p>
          <h2 className="mt-1 text-2xl font-black text-ink">Sign in to Mayajal</h2>
          <form className="mt-7 space-y-4" onSubmit={submit}>
            <label className="block text-sm font-bold text-ink/72">Username<input value={username} onChange={(event) => setUsername(event.target.value)} className="mt-2 block min-h-11 w-full rounded-md border border-ink/15 px-3 text-ink outline-none focus:border-fern" autoComplete="username" /></label>
            <label className="block text-sm font-bold text-ink/72">Password<input value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 block min-h-11 w-full rounded-md border border-ink/15 px-3 text-ink outline-none focus:border-fern" type="password" autoComplete="current-password" /></label>
            {error ? <p className="rounded-md bg-clay/10 px-3 py-2 text-sm font-semibold text-clay">{error}</p> : null}
            <button type="submit" disabled={submitting} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-canopy px-4 text-sm font-bold text-white hover:bg-fern disabled:cursor-not-allowed disabled:opacity-50">{submitting ? "Signing in" : "Sign in"}<ArrowRight size={17} /></button>
          </form>
          <div className="mt-8 border-t border-ink/10 pt-5">
            <p className="text-xs font-bold uppercase text-ink/45">Training accounts</p>
            <div className="mt-3 grid gap-2">
              {accounts.map((account) => (
                <button key={account.username} type="button" onClick={() => { setUsername(account.username); setPassword(account.password); setError(""); }} className="grid gap-1 rounded-md border border-ink/10 p-3 text-left transition hover:border-fern/50 hover:bg-cloud sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-3">
                  <span><span className="block text-sm font-black text-ink">{roleProfiles[account.role].label}</span><span className="mt-1 block text-xs text-ink/54">{account.name}</span></span>
                  <code className="text-xs font-semibold text-ink/68">{account.username}</code>
                  <code className="text-xs font-semibold text-ink/68">{account.password}</code>
                </button>
              ))}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function Home() {
  const [account, setAccount] = useState<Account | null>(null);
  const [apiUrl, setApiUrl] = useState("http://127.0.0.1:8000");
  const [activeNav, setActiveNav] = useState("My learning");
  const role = account?.role ?? "student";

  useEffect(() => {
    fetch("/api/runtime-config")
      .then((response) => response.json())
      .then((config: { apiUrl?: string }) => setApiUrl(config.apiUrl ?? "Service endpoint unavailable"))
      .catch(() => setApiUrl("Service endpoint unavailable"));
  }, []);

  const heading = useMemo(() => {
    if (!account) return null;
    if (role === "student") return ["Welcome back, " + account.name.split(" ")[0], "Pick up an assigned lab or build a personal scenario from the approved machine library."];
    if (role === "teacher") return ["Teaching workspace", "Create classroom labs, support learners, and review activity across your cohorts."];
    return ["Platform control", "Manage lab operations, the machine fleet, and access across the Mayajal environment."];
  }, [account, role]);

  async function handleSignIn(username: string, password: string) {
    const result = await signIn(apiUrl, username, password);
    const selected = accounts.find((candidate) => candidate.username === username);
    if (!selected) throw new Error("This account is not configured for the workspace.");
    setAccount({ ...selected, name: result.user.name, initials: result.user.initials, role: result.user.role });
    setActiveNav(roleNavigation[result.user.role][0].label);
  }

  if (!account) return <SignIn onSignIn={handleSignIn} />;

  const Workspace = role === "student" ? StudentWorkspace : role === "teacher" ? TeacherWorkspace : AdminWorkspace;

  return (
    <main className="min-h-screen">
      <div className="dashboard-grid min-h-screen">
        <aside className="border-r border-ink/10 bg-[#f8fbf8] p-5 lg:sticky lg:top-0 lg:h-screen">
          <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-lg bg-canopy text-white"><Shield size={23} /></span><div><p className="text-lg font-black text-ink">Mayajal</p><p className="text-xs font-medium text-ink/54">Cyber lab workspace</p></div></div>
          <nav className="mt-8 space-y-1">{roleNavigation[role].map((item, index) => { const Icon = item.icon; return <button type="button" key={item.label} onClick={() => setActiveNav(item.label)} className={clsx("flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-sm font-semibold", activeNav === item.label || (index === 0 && !activeNav) ? "bg-canopy text-white" : "text-ink/68 hover:bg-canopy/8 hover:text-ink")}><Icon size={18} />{item.label}</button>; })}</nav>
          <div className="mt-8 rounded-lg border border-ink/10 bg-white p-4"><p className="text-xs font-bold uppercase text-ink/48">Service endpoint</p><p className="mt-2 break-all rounded-md bg-cloud px-3 py-2 text-xs font-semibold text-ink/70">{apiUrl}</p></div>
          <button type="button" onClick={() => setAccount(null)} className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-md px-3 text-sm font-bold text-ink/62 hover:bg-ink/5"><LogOut size={17} />Sign out</button>
        </aside>
        <section className="min-w-0 p-4 sm:p-6 xl:p-8">
          <header className="flex flex-col gap-4 border-b border-ink/10 pb-6 sm:flex-row sm:items-start sm:justify-between">
            <div><p className="text-xs font-bold uppercase text-ink/44">{roleProfiles[role].label} workspace</p><h1 className="mt-1 text-3xl font-black text-ink sm:text-4xl">{heading?.[0]}</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-ink/60 sm:text-base">{heading?.[1]}</p></div>
            <div className="flex items-center gap-3 rounded-lg border border-ink/10 bg-white p-2"><span className="grid h-10 w-10 place-items-center rounded-full bg-canopy text-sm font-black text-white">{account.initials}</span><div><p className="text-sm font-black text-ink">{account.name}</p><p className="text-xs font-semibold text-fern">{roleProfiles[role].label}</p></div></div>
          </header>
          <section className="mt-6 grid gap-4 md:grid-cols-3">{roleMetrics[role].map((metric) => <MetricCard key={metric.label} metric={metric} />)}</section>
          <section className="mt-6">{role === "student" ? <StudentPortal apiUrl={apiUrl} view={activeNav} /> : <ManagementPortal apiUrl={apiUrl} role={role} view={activeNav} />}</section>
        </section>
      </div>
    </main>
  );
}
