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
  description: string;
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
};

export type ApiScenario = {
  id: string;
  name: string;
  status: string;
  machine_ids: string[];
  updated_at: string;
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
  const response = await fetch(trimUrl(apiUrl) + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: "Bearer " + accessToken } : {}), ...init?.headers },
  });
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
  return request<{ lab_id: string; status: string; message: string; access_url: string }>(
    apiUrl,
    "/labs/" + labId + "/start",
    { method: "POST" },
  );
}

export function saveScenario(apiUrl: string, name: string, machineIds: string[]) {
  return request<ApiScenario>(apiUrl, "/student/scenarios", {
    method: "POST",
    body: JSON.stringify({ name, machine_ids: machineIds }),
  });
}


export type TeacherDashboard = {
  labs: ApiLab[];
  machines: ApiMachine[];
  students: { id: string; name: string; cohort: string; active_labs: number; progress: number }[];
  reviews: { id: string; student: string; lab: string; state: string }[];
};

export type AdminDashboard = {
  labs: ApiLab[];
  machines: ApiMachine[];
  users: { id: string; name: string; username: string; role: "student" | "teacher" | "admin"; status: string }[];
  settings: { id: string; label: string; enabled: boolean }[];
  health: { name: string; value: string }[];
};

export function getTeacherDashboard(apiUrl: string) {
  return request<TeacherDashboard>(apiUrl, "/teacher/dashboard");
}

export function createTeacherLab(apiUrl: string, name: string) {
  return request<ApiLab>(apiUrl, "/teacher/labs", { method: "POST", body: JSON.stringify({ name }) });
}

export function completeReview(apiUrl: string, reviewId: string) {
  return request<{ id: string; message: string }>(apiUrl, "/teacher/reviews/" + reviewId, { method: "POST" });
}

export function getAdminDashboard(apiUrl: string) {
  return request<AdminDashboard>(apiUrl, "/admin/dashboard");
}

export function createAdminMachine(apiUrl: string, name: string, os_type: string) {
  return request<ApiMachine>(apiUrl, "/admin/machines", { method: "POST", body: JSON.stringify({ name, os_type }) });
}

export function changeUserRole(apiUrl: string, userId: string, role: "student" | "teacher" | "admin") {
  return request<{ id: string; role: "student" | "teacher" | "admin"; message: string }>(apiUrl, "/admin/users/" + userId + "/role", { method: "PATCH", body: JSON.stringify({ role }) });
}

export function changeSetting(apiUrl: string, settingId: string, enabled: boolean) {
  return request<{ id: string; enabled: boolean; message: string }>(apiUrl, "/admin/settings/" + settingId, { method: "PATCH", body: JSON.stringify({ enabled }) });
}
