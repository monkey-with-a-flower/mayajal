export type ApiUser = {
  id: string;
  name: string;
  role: "student" | "teacher" | "admin";
  initials: string;
};

export type ApiMachine = {
  id: string;
  name: string;
  os_type: string;
  imageUrl: string;
  source_type: "dockerhub" | "local" | "custom";
  description: string;
  hostname: string | null;
  command: string | null;
  entrypoint: string | null;
  working_dir: string | null;
  run_as: string | null;
  restart_policy: "no" | "always" | "on-failure" | "unless-stopped";
  privileged: boolean;
  tty: boolean;
  stdin_open: boolean;
  ports: string[];
  volumes: string[];
  environment: Record<string, string>;
  labels: Record<string, string>;
  dns: string[];
  extra_hosts: string[];
  cap_add: string[];
  network_aliases: string[];
  added_by: string;
};

export type ApiLab = {
  id: string;
  name: string;
  description: string;
  status: "ready" | "running" | "locked";
  owner: string;
  level: string;
  runtime: string;
  progress: number;
  next_step: string;
  machine_ids: string[];
  tasks: string[];
  student_ids: string[];
  group_ids: string[];
  assigned_student_ids: string[];
  assigned_count: number;
  running_sessions: number;
};

export type ApiStudentGroup = {
  id: string;
  name: string;
  student_ids: string[];
  student_count: number;
  lab_count: number;
};

export type ApiScenario = {
  id: string;
  name: string;
  status: string;
  machine_ids: string[];
  updated_at: string;
};

export type ApiLabSession = {
  id: string;
  lab_id: string;
  student_id: string;
  status: "running" | "stopped";
  access_url: string | null;
  started_at: string;
  stopped_at: string | null;
};

export type AttackReport = {
  session_id: string;
  generated_at: string;
  event_count: number;
  summary: string;
  attack_chain: {
    tactic: string;
    technique_id: string;
    technique: string;
    rationale: string;
    event_count: number;
    evidence: Record<string, unknown>[];
  }[];
};

export type StudentDashboard = {
  student: ApiUser;
  assignments: ApiLab[];
  machines: ApiMachine[];
  scenarios: ApiScenario[];
  activity: { id: string; title: string; detail: string; when: string }[];
};

export type LoginResult = {
  access_token: string;
  token_type: string;
  user: ApiUser;
};

let accessToken = "";

function trimUrl(url: string) {
  return url.replace(/\/$/, "");
}

async function request<T>(apiUrl: string, path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(trimUrl(apiUrl) + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: "Bearer " + accessToken } : {}), ...init?.headers },
    });
  } catch (error) {
    throw new Error("Cannot reach the Mayajal API at " + trimUrl(apiUrl) + ". Make sure the backend is running on port 8001 and reachable from this browser.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "The service could not complete this request.");
  }
  return response.json() as Promise<T>;
}

export async function signIn(apiUrl: string, username: string, password: string) {
  const result = await request<LoginResult>(apiUrl, "/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  accessToken = result.access_token;
  return result;
}

export function getStudentDashboard(apiUrl: string) {
  return request<StudentDashboard>(apiUrl, "/student/dashboard");
}

export function startLab(apiUrl: string, labId: string) {
  return request<{ lab_id: string; status: string; message: string; wireguard_config: string; wireguard_filename: string; output?: string }>(
    apiUrl,
    "/labs/" + labId + "/start",
    { method: "POST" },
  );
}

async function streamRequest(apiUrl: string, path: string, onChunk: (chunk: string) => void) {
  let response: Response;
  try {
    response = await fetch(trimUrl(apiUrl) + path, {
      method: "POST",
      headers: { ...(accessToken ? { Authorization: "Bearer " + accessToken } : {}) },
    });
  } catch (error) {
    throw new Error("Cannot reach the Mayajal API at " + trimUrl(apiUrl) + ". Make sure the backend is running on port 8001 and reachable from this browser.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "The service could not complete this request.");
  }
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let received = "";
  while (true) {
    let result: ReadableStreamReadResult<Uint8Array>;
    try {
      result = await reader.read();
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : "The streamed response was interrupted.");
    }
    const { value, done } = result;
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    received += chunk;
    onChunk(chunk);
  }
  const tail = decoder.decode();
  if (tail) {
    received += tail;
    onChunk(tail);
  }
  const errorLine = received.split(/\r?\n/).find((line) => line.startsWith("Error: "));
  if (errorLine) throw new Error(errorLine.slice("Error: ".length));
}

export function startLabStream(apiUrl: string, labId: string, onChunk: (chunk: string) => void) {
  return streamRequest(apiUrl, "/labs/" + labId + "/start?stream=true", onChunk);
}

export function stopLab(apiUrl: string, labId: string) {
  return request<{ lab_id: string; status: "stopped" | "running"; stopped_at: string | null }>(
    apiUrl,
    "/labs/" + labId + "/stop",
    { method: "POST" },
  );
}

export function stopLabStream(apiUrl: string, labId: string, onChunk: (chunk: string) => void) {
  return streamRequest(apiUrl, "/labs/" + labId + "/stop?stream=true", onChunk);
}

export function getLabVpn(apiUrl: string, labId: string) {
  return request<{ lab_id: string; wireguard_config: string; wireguard_filename: string }>(
    apiUrl,
    "/labs/" + labId + "/vpn",
  );
}

export function listLabSessions(apiUrl: string, labId: string) {
  return request<ApiLabSession[]>(apiUrl, "/labs/" + labId + "/sessions");
}

export function getAttackReport(apiUrl: string, sessionId: string) {
  return request<AttackReport>(apiUrl, "/sessions/" + sessionId + "/attack-report");
}

export function saveScenario(apiUrl: string, name: string, machineIds: string[]) {
  return request<ApiScenario>(apiUrl, "/student/scenarios", {
    method: "POST",
    body: JSON.stringify({ name, machine_ids: machineIds }),
  });
}

export function updateScenario(apiUrl: string, scenarioId: string, name: string, machineIds: string[]) {
  return request<ApiScenario>(apiUrl, "/student/scenarios/" + scenarioId, {
    method: "PATCH",
    body: JSON.stringify({ name, machine_ids: machineIds }),
  });
}

export function deleteScenario(apiUrl: string, scenarioId: string) {
  return request<{ id: string; message: string }>(apiUrl, "/student/scenarios/" + scenarioId, { method: "DELETE" });
}


export type TeacherDashboard = {
  labs: ApiLab[];
  machines: ApiMachine[];
  students: { id: string; name: string; cohort: string; active_labs: number; running_labs: number; progress: number }[];
  groups: ApiStudentGroup[];
  metrics: { students: number; labs: number; running_sessions: number };
  reviews: { id: string; student: string; lab: string; state: string }[];
};

export type AdminDashboard = {
  labs: ApiLab[];
  machines: ApiMachine[];
  users: { id: string; name: string; username: string; role: "student" | "teacher" | "admin"; status: string }[];
  groups: ApiStudentGroup[];
  running_sessions: { id: string; lab_id: string; lab: string; student_id: string; student: string; status: string; started_at: string }[];
  metrics: { students: number; teachers: number; labs: number; running_sessions: number };
  settings: { id: string; label: string; enabled: boolean }[];
  health: { name: string; value: string }[];
};

export function getTeacherDashboard(apiUrl: string) {
  return request<TeacherDashboard>(apiUrl, "/teacher/dashboard");
}

export type TeacherLabInput = {
  name: string;
  description: string;
  machine_ids: string[];
  tasks: string[];
  student_ids: string[];
  group_ids: string[];
  publish: boolean;
};

export function createTeacherLab(apiUrl: string, lab: TeacherLabInput) {
  return request<ApiLab>(apiUrl, "/teacher/labs", { method: "POST", body: JSON.stringify(lab) });
}

export function updateTeacherLab(apiUrl: string, lab: Pick<ApiLab, "id" | "name" | "description" | "machine_ids" | "tasks" | "status" | "student_ids" | "group_ids">) {
  return request<ApiLab>(apiUrl, "/teacher/labs/" + lab.id, {
    method: "PATCH",
    body: JSON.stringify({ name: lab.name, description: lab.description, machine_ids: lab.machine_ids, tasks: lab.tasks, student_ids: lab.student_ids, group_ids: lab.group_ids, publish: lab.status !== "locked" }),
  });
}

export function deleteTeacherLab(apiUrl: string, labId: string) {
  return request<{ id: string; message: string }>(apiUrl, "/teacher/labs/" + labId, { method: "DELETE" });
}

export function createTeacherGroup(apiUrl: string, group: { name: string; student_ids: string[] }) {
  return request<ApiStudentGroup>(apiUrl, "/teacher/groups", { method: "POST", body: JSON.stringify(group) });
}

export function updateTeacherGroup(apiUrl: string, groupId: string, group: { name: string; student_ids: string[] }) {
  return request<ApiStudentGroup>(apiUrl, "/teacher/groups/" + groupId, { method: "PATCH", body: JSON.stringify(group) });
}

export function deleteTeacherGroup(apiUrl: string, groupId: string) {
  return request<{ id: string; message: string }>(apiUrl, "/teacher/groups/" + groupId, { method: "DELETE" });
}

export function completeReview(apiUrl: string, reviewId: string) {
  return request<{ id: string; message: string }>(apiUrl, "/teacher/reviews/" + reviewId, { method: "POST" });
}

export function getAdminDashboard(apiUrl: string) {
  return request<AdminDashboard>(apiUrl, "/admin/dashboard");
}

export type MachineInput = {
  name: string;
  image_url: string;
  source_type: "dockerhub" | "local" | "custom";
  os_type: string;
  description: string;
  hostname?: string | null;
  command?: string | null;
  entrypoint?: string | null;
  working_dir?: string | null;
  run_as?: string | null;
  restart_policy: "no" | "always" | "on-failure" | "unless-stopped";
  privileged: boolean;
  tty: boolean;
  stdin_open: boolean;
  ports: string[];
  volumes: string[];
  environment: Record<string, string>;
  labels: Record<string, string>;
  dns: string[];
  extra_hosts: string[];
  cap_add: string[];
  network_aliases: string[];
};

export function createAdminMachine(apiUrl: string, machine: MachineInput) {
  return request<ApiMachine>(apiUrl, "/admin/machines", { method: "POST", body: JSON.stringify(machine) });
}

export function updateAdminMachine(apiUrl: string, machineId: string, machine: MachineInput) {
  return request<ApiMachine>(apiUrl, "/admin/machines/" + machineId, { method: "PATCH", body: JSON.stringify(machine) });
}

export function changeUserRole(apiUrl: string, userId: string, role: "student" | "teacher" | "admin") {
  return request<{ id: string; role: "student" | "teacher" | "admin"; message: string }>(apiUrl, "/admin/users/" + userId + "/role", { method: "PATCH", body: JSON.stringify({ role }) });
}

export function changeSetting(apiUrl: string, settingId: string, enabled: boolean) {
  return request<{ id: string; enabled: boolean; message: string }>(apiUrl, "/admin/settings/" + settingId, { method: "PATCH", body: JSON.stringify({ enabled }) });
}
