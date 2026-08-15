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
  attachment: string | null;
  attachments: string[];
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
  detection_profile: string | null;
  added_by: string;
  repository_url: string | null;
  repository_ref: string | null;
  repository_path: string | null;
  source_digest: string | null;
  import_version: number;
  last_imported_at: string | null;
  memory_limit: string;
  cpu_limit: number;
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
  grading_tasks?: GradingTask[];
  questions: { id: string; prompt: string; answer: string }[];
  student_ids: string[];
  group_ids: string[];
  assigned_student_ids: string[];
  assigned_count: number;
  running_sessions: number;
  submission_status: "awaiting_review" | "finalized" | null;
  score: number | null;
  max_score: number;
  lab_cidr?: string | null;
};

export type ApiSubmission = {
  id: string;
  lab_id: string;
  lab: string;
  student_id: string;
  student: string;
  status: "awaiting_review" | "finalized";
  state: string;
  auto_score: number;
  max_score: number;
  final_score: number | null;
  feedback: string;
  submitted_at: string;
  finalized_at: string | null;
  results: {
    task_id: string;
    prompt: string;
    grading_type: string;
    answer?: string;
    correct: boolean | null;
    points: number;
    awarded_points: number;
  }[];
};

export type GradingTask = {
  id?: string;
  prompt: string;
  grading_type: "exact" | "contains" | "regex" | "manual";
  expected_answer: string;
  points: number;
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
  status: "saved" | "running";
  running_session_id: string | null;
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
  telemetry_event_count: number;
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

export type ReportType = "academic" | "professional";

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

async function request<T>(
  apiUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(trimUrl(apiUrl) + path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: "Bearer " + accessToken } : {}),
        ...init?.headers,
      },
    });
  } catch (error) {
    throw new Error(
      "Cannot reach the Mayajal API at " + trimUrl(apiUrl) +
        ". Make sure the backend is running on port 8001 and reachable from this browser.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail ?? "The service could not complete this request.",
    );
  }
  return response.json() as Promise<T>;
}

export async function signIn(
  apiUrl: string,
  username: string,
  password: string,
) {
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
  return request<
    {
      lab_id: string;
      status: string;
      message: string;
      wireguard_config: string;
      wireguard_filename: string;
      attachments: LabAttachment[];
      lab_cidr: string | null;
      output?: string;
    }
  >(
    apiUrl,
    "/labs/" + labId + "/start",
    { method: "POST" },
  );
}

export type LabAttachment = {
  machine_id: string;
  machine_name: string;
  filename: string;
  download_url: string;
};

export function getLabAttachments(apiUrl: string, labId: string) {
  return request<{ lab_id: string; attachments: LabAttachment[] }>(
    apiUrl,
    "/labs/" + labId + "/attachments",
  );
}

export async function downloadLabAttachment(
  apiUrl: string,
  attachment: LabAttachment,
) {
  const response = await fetch(trimUrl(apiUrl) + attachment.download_url, {
    headers: {
      ...(accessToken ? { Authorization: "Bearer " + accessToken } : {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to download the attachment.");
  }
  return { filename: attachment.filename, blob: await response.blob() };
}

export function saveLabAnswers(
  apiUrl: string,
  labId: string,
  answers: Record<string, string>,
) {
  return request<
    { lab_id: string; questions: ApiLab["questions"]; message: string }
  >(apiUrl, "/student/labs/" + labId + "/answers", {
    method: "PUT",
    body: JSON.stringify({ answers }),
  });
}

export function submitLab(apiUrl: string, labId: string) {
  return request<ApiSubmission & { message: string }>(
    apiUrl,
    "/student/labs/" + labId + "/submit",
    { method: "POST" },
  );
}

async function streamRequest(
  apiUrl: string,
  path: string,
  onChunk: (chunk: string) => void,
) {
  let response: Response;
  try {
    response = await fetch(trimUrl(apiUrl) + path, {
      method: "POST",
      headers: {
        ...(accessToken ? { Authorization: "Bearer " + accessToken } : {}),
      },
    });
  } catch (error) {
    throw new Error(
      "Cannot reach the Mayajal API at " + trimUrl(apiUrl) +
        ". Make sure the backend is running on port 8001 and reachable from this browser.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail ?? "The service could not complete this request.",
    );
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
      throw new Error(
        error instanceof Error
          ? error.message
          : "The streamed response was interrupted.",
      );
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
  const errorLine = received.split(/\r?\n/).find((line) =>
    line.startsWith("Error: ")
  );
  if (errorLine) throw new Error(errorLine.slice("Error: ".length));
}

export function startLabStream(
  apiUrl: string,
  labId: string,
  onChunk: (chunk: string) => void,
) {
  return streamRequest(
    apiUrl,
    "/labs/" + labId + "/start?stream=true",
    onChunk,
  );
}

export function stopLab(apiUrl: string, labId: string) {
  return request<
    { lab_id: string; status: "stopped" | "running"; stopped_at: string | null }
  >(
    apiUrl,
    "/labs/" + labId + "/stop",
    { method: "POST" },
  );
}

export function stopLabStream(
  apiUrl: string,
  labId: string,
  onChunk: (chunk: string) => void,
) {
  return streamRequest(apiUrl, "/labs/" + labId + "/stop?stream=true", onChunk);
}

export function getLabVpn(apiUrl: string, labId: string) {
  return request<
    {
      lab_id: string;
      wireguard_config: string;
      wireguard_filename: string;
      lab_cidr: string | null;
    }
  >(
    apiUrl,
    "/labs/" + labId + "/vpn",
  );
}

export function listLabSessions(apiUrl: string, labId: string) {
  return request<ApiLabSession[]>(apiUrl, "/labs/" + labId + "/sessions");
}

export function getAttackReport(apiUrl: string, sessionId: string) {
  return request<AttackReport>(
    apiUrl,
    "/sessions/" + sessionId + "/attack-report",
  );
}

export async function openAttackReport(
  apiUrl: string,
  sessionId: string,
  reportType: ReportType,
) {
  const reportWindow = window.open("", "_blank");
  if (!reportWindow) throw new Error("Allow pop-ups to open the report page.");
  reportWindow.document.title = "Loading Mayajal report";
  reportWindow.document.body.textContent = "Loading report…";
  const response = await fetch(
    trimUrl(apiUrl) + "/sessions/" + sessionId +
      "/attack-report/view?report_type=" + reportType,
    {
      headers: {
        ...(accessToken ? { Authorization: "Bearer " + accessToken } : {}),
      },
    },
  );
  if (!response.ok) {
    reportWindow.close();
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to generate the report page.");
  }
  const reportUrl = URL.createObjectURL(
    new Blob([await response.text()], { type: "text/html" }),
  );
  reportWindow.location.href = reportUrl;
}

export function saveScenario(
  apiUrl: string,
  name: string,
  machineIds: string[],
) {
  return request<ApiScenario>(apiUrl, "/student/scenarios", {
    method: "POST",
    body: JSON.stringify({ name, machine_ids: machineIds }),
  });
}

export function updateScenario(
  apiUrl: string,
  scenarioId: string,
  name: string,
  machineIds: string[],
) {
  return request<ApiScenario>(apiUrl, "/student/scenarios/" + scenarioId, {
    method: "PATCH",
    body: JSON.stringify({ name, machine_ids: machineIds }),
  });
}

export function deleteScenario(apiUrl: string, scenarioId: string) {
  return request<{ id: string; message: string }>(
    apiUrl,
    "/student/scenarios/" + scenarioId,
    { method: "DELETE" },
  );
}

export function startScenario(apiUrl: string, scenarioId: string) {
  return request<
    {
      id: string;
      scenario_id: string;
      status: "running";
      wireguard_config: string;
      wireguard_filename: string;
      message: string;
    }
  >(apiUrl, "/student/scenarios/" + scenarioId + "/start", { method: "POST" });
}

export function getScenarioVpn(apiUrl: string, scenarioId: string) {
  return request<
    {
      scenario_id: string;
      wireguard_config: string;
      wireguard_filename: string;
    }
  >(apiUrl, "/student/scenarios/" + scenarioId + "/vpn");
}

export function stopScenario(apiUrl: string, scenarioId: string) {
  return request<
    {
      id: string;
      scenario_id: string;
      status: "stopped";
      stopped_at: string;
      message: string;
    }
  >(apiUrl, "/student/scenarios/" + scenarioId + "/stop", { method: "POST" });
}

export type TeacherDashboard = {
  labs: ApiLab[];
  machines: ApiMachine[];
  students: {
    id: string;
    name: string;
    cohort: string;
    active_labs: number;
    running_labs: number;
    progress: number;
  }[];
  groups: ApiStudentGroup[];
  metrics: { students: number; labs: number; running_sessions: number };
  reviews: ApiSubmission[];
};

export type AdminDashboard = {
  labs: ApiLab[];
  machines: ApiMachine[];
  users: {
    id: string;
    name: string;
    username: string;
    role: "student" | "teacher" | "admin";
    status: string;
  }[];
  groups: ApiStudentGroup[];
  running_sessions: {
    id: string;
    lab_id: string;
    lab: string;
    student_id: string;
    student: string;
    status: string;
    started_at: string;
  }[];
  metrics: {
    students: number;
    teachers: number;
    labs: number;
    running_sessions: number;
  };
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
  tasks: GradingTask[];
  student_ids: string[];
  group_ids: string[];
  publish: boolean;
};

export function createTeacherLab(apiUrl: string, lab: TeacherLabInput) {
  return request<ApiLab>(apiUrl, "/teacher/labs", {
    method: "POST",
    body: JSON.stringify(lab),
  });
}

export function updateTeacherLab(
  apiUrl: string,
  lab: Pick<
    ApiLab,
    | "id"
    | "name"
    | "description"
    | "machine_ids"
    | "grading_tasks"
    | "status"
    | "student_ids"
    | "group_ids"
  >,
) {
  return request<ApiLab>(apiUrl, "/teacher/labs/" + lab.id, {
    method: "PATCH",
    body: JSON.stringify({
      name: lab.name,
      description: lab.description,
      machine_ids: lab.machine_ids,
      tasks: lab.grading_tasks ?? [],
      student_ids: lab.student_ids,
      group_ids: lab.group_ids,
      publish: lab.status !== "locked",
    }),
  });
}

export function deleteTeacherLab(apiUrl: string, labId: string) {
  return request<{ id: string; message: string }>(
    apiUrl,
    "/teacher/labs/" + labId,
    { method: "DELETE" },
  );
}

export function createTeacherGroup(
  apiUrl: string,
  group: { name: string; student_ids: string[] },
) {
  return request<ApiStudentGroup>(apiUrl, "/teacher/groups", {
    method: "POST",
    body: JSON.stringify(group),
  });
}

export function updateTeacherGroup(
  apiUrl: string,
  groupId: string,
  group: { name: string; student_ids: string[] },
) {
  return request<ApiStudentGroup>(apiUrl, "/teacher/groups/" + groupId, {
    method: "PATCH",
    body: JSON.stringify(group),
  });
}

export function deleteTeacherGroup(apiUrl: string, groupId: string) {
  return request<{ id: string; message: string }>(
    apiUrl,
    "/teacher/groups/" + groupId,
    { method: "DELETE" },
  );
}

export function completeReview(
  apiUrl: string,
  reviewId: string,
  finalScore?: number,
  feedback = "",
) {
  return request<ApiSubmission & { message: string }>(
    apiUrl,
    "/teacher/reviews/" + reviewId,
    {
      method: "POST",
      body: JSON.stringify({ final_score: finalScore, feedback }),
    },
  );
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
  attachment?: string | null;
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
  detection_profile?: string | null;
  memory_limit: string;
  cpu_limit: number;
};

export function createAdminMachine(apiUrl: string, machine: MachineInput) {
  return request<ApiMachine>(apiUrl, "/admin/machines", {
    method: "POST",
    body: JSON.stringify(machine),
  });
}

export type GitHubMachineImportInput = {
  repository_url: string;
  ref: string;
  machine_path: string;
};

export type GitHubMachineFolder = {
  path: string;
  name: string;
  os_type: string;
  description: string;
  image: string;
};

export function discoverGitHubMachines(
  apiUrl: string,
  input: Pick<GitHubMachineImportInput, "repository_url" | "ref">,
) {
  return request<
    { repository_url: string; ref: string; machines: GitHubMachineFolder[] }
  >(apiUrl, "/admin/machines/github-folders", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function importGitHubMachine(
  apiUrl: string,
  input: GitHubMachineImportInput,
) {
  return request<ApiMachine>(apiUrl, "/admin/machines/import-github", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAdminMachine(
  apiUrl: string,
  machineId: string,
  machine: MachineInput,
) {
  return request<ApiMachine>(apiUrl, "/admin/machines/" + machineId, {
    method: "PATCH",
    body: JSON.stringify(machine),
  });
}

export function refreshGitHubMachine(apiUrl: string, machineId: string) {
  return request<ApiMachine & { message: string }>(
    apiUrl,
    "/admin/machines/" + machineId + "/refresh-github",
    { method: "POST" },
  );
}

export function getMachineVersions(apiUrl: string, machineId: string) {
  return request<
    {
      id: string;
      version: number;
      source_digest: string;
      repository_url: string;
      repository_ref: string;
      repository_path: string;
      imported_at: string;
      imported_by: string;
    }[]
  >(apiUrl, "/admin/machines/" + machineId + "/versions");
}

export function changeUserRole(
  apiUrl: string,
  userId: string,
  role: "student" | "teacher" | "admin",
) {
  return request<
    { id: string; role: "student" | "teacher" | "admin"; message: string }
  >(apiUrl, "/admin/users/" + userId + "/role", {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function changeSetting(
  apiUrl: string,
  settingId: string,
  enabled: boolean,
) {
  return request<{ id: string; enabled: boolean; message: string }>(
    apiUrl,
    "/admin/settings/" + settingId,
    { method: "PATCH", body: JSON.stringify({ enabled }) },
  );
}
