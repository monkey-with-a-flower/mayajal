import {
  BookOpenCheck,
  Boxes,
  ClipboardCheck,
  GraduationCap,
  KeyRound,
  Network,
  PlayCircle,
  ShieldCheck,
  Users,
} from "lucide-react";

export type Role = "student" | "teacher" | "admin";

export type Account = {
  username: string;
  password: string;
  name: string;
  role: Role;
  initials: string;
};

export type Permission = {
  label: string;
  student: boolean;
  teacher: boolean;
  admin: boolean;
};

export const roleProfiles: Record<
  Role,
  {
    label: string;
    summary: string;
    badge: string;
  }
> = {
  student: {
    label: "Student",
    summary:
      "Can run assigned labs and assemble personal scenarios from approved vulnerable machines.",
    badge: "Least privilege",
  },
  teacher: {
    label: "Teacher",
    summary:
      "Can create labs, publish scenarios, manage vulnerable machines, and review student work.",
    badge: "Builder access",
  },
  admin: {
    label: "Admin",
    summary:
      "Can manage every lab, machine, user, role, and platform-wide configuration.",
    badge: "Full privilege",
  },
};

export const accounts: Account[] = [
  {
    username: "student.maya",
    password: "Student!2026",
    name: "Maya Patel",
    role: "student",
    initials: "MP",
  },
  {
    username: "teacher.asha",
    password: "Teacher!2026",
    name: "Asha Rana",
    role: "teacher",
    initials: "AR",
  },
  {
    username: "admin.samir",
    password: "Admin!2026",
    name: "Samir Khan",
    role: "admin",
    initials: "SK",
  },
];

export const permissions: Permission[] = [
  { label: "Start assigned labs", student: true, teacher: true, admin: true },
  { label: "Create personal lab scenarios", student: true, teacher: true, admin: true },
  { label: "Create classroom labs", student: false, teacher: true, admin: true },
  { label: "Add vulnerable machines", student: false, teacher: true, admin: true },
  { label: "Edit role and user access", student: false, teacher: true, admin: true },
  { label: "Manage platform settings", student: false, teacher: true, admin: true },
];

export const navigation = [
  { label: "Command", icon: ShieldCheck },
  { label: "Labs", icon: BookOpenCheck },
  { label: "Builder", icon: Boxes },
  { label: "Machines", icon: Network },
  { label: "Access", icon: KeyRound },
  { label: "Users", icon: Users },
];

export const stats = [
  { label: "Active labs", value: "18", detail: "+4 today", icon: PlayCircle },
  { label: "Student starts", value: "126", detail: "last 7 days", icon: GraduationCap },
  { label: "Machine images", value: "42", detail: "approved pool", icon: Network },
  { label: "Reviews due", value: "9", detail: "teacher queue", icon: ClipboardCheck },
];

export const labs = [
  {
    title: "Web Exploit Basics",
    owner: "Asha Rana",
    level: "Beginner",
    status: "Published",
    machines: ["DVWA", "Kali Workstation"],
    runtime: "45 min",
    starts: 38,
    accent: "bg-mint",
  },
  {
    title: "Windows Privilege Path",
    owner: "Morgan Lee",
    level: "Intermediate",
    status: "Draft",
    machines: ["WinServer 2019", "Attacker Box"],
    runtime: "90 min",
    starts: 14,
    accent: "bg-sun",
  },
  {
    title: "Blue Team Packet Hunt",
    owner: "Security Admin",
    level: "Advanced",
    status: "Published",
    machines: ["Suricata Sensor", "Ubuntu Target"],
    runtime: "60 min",
    starts: 22,
    accent: "bg-clay",
  },
];

export const machines = [
  { name: "Kali Workstation", os: "Linux", image: "kalilinux/kali-rolling", addedBy: "Admin" },
  { name: "DVWA", os: "Linux", image: "vulnerables/web-dvwa", addedBy: "Teacher" },
  { name: "Suricata Sensor", os: "Linux", image: "jasonish/suricata", addedBy: "Admin" },
  { name: "WinServer 2019", os: "Windows", image: "lab/windows-server-2019", addedBy: "Teacher" },
];
