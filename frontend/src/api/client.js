import axios from "axios";

// In dev, Vite proxies /api -> Flask (see vite.config.js), so a relative
// base URL works in both dev and a same-origin production deployment.
const client = axios.create({
  baseURL: "/api",
  timeout: 10000,
});

// Central error normalization so components can just check `err.message`.
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    // A blob-responseType request (report downloads) that errors still
    // gets a Blob back as error.response.data, not parsed JSON — without
    // this, every report-download failure would show the generic
    // "Unexpected network error" instead of the backend's real message.
    if (error.response?.data instanceof Blob && error.response.data.type === "application/json") {
      try {
        const text = await error.response.data.text();
        const parsed = JSON.parse(text);
        return Promise.reject(new Error(parsed.error || "Unexpected network error"));
      } catch {
        // fall through to the generic handling below
      }
    }
    const message =
      error.response?.data?.error ||
      error.message ||
      "Unexpected network error";
    return Promise.reject(new Error(message));
  }
);

export const api = {
  health: () => client.get("/health").then((r) => r.data.data),

  listStudents: () => client.get("/students").then((r) => r.data.data),

  registerStudent: (name, rollNumber, imagesBase64) =>
    client
      .post("/students/register", {
        name,
        roll_number: rollNumber,
        images: imagesBase64,
      })
      .then((r) => r.data.data),

  deleteStudent: (studentId) =>
    client.delete(`/students/${studentId}`).then((r) => r.data.data),

  processFrame: (imageBase64) =>
    client
      .post("/process-frame", { image: imageBase64 })
      .then((r) => r.data.data),

  attendanceToday: () =>
    client.get("/attendance/today").then((r) => r.data.data),

  attendanceRange: (start, end) =>
    client
      .get("/attendance/range", { params: { start, end } })
      .then((r) => r.data.data),

  attentionHistory: (studentId, date) =>
    client
      .get(`/attention/history/${studentId}`, { params: { date } })
      .then((r) => r.data.data),

  classSummary: () =>
    client.get("/analytics/class-summary").then((r) => r.data.data),

  // Real, Firestore-aggregated daily history (avg attention / low-attention
  // count per day). Returns { days: [], storage_available: false } instead
  // of fake data when Firebase isn't configured — never fabricate history.
  dailyAnalytics: (days = 7) =>
    client.get("/analytics/daily", { params: { days } }).then((r) => r.data.data),

  recentAlerts: (limit = 50) =>
    client
      .get("/alerts/recent", { params: { limit } })
      .then((r) => r.data.data),

  esp32Status: () =>
    client.get("/devices/esp32/status").then((r) => r.data.data),

  systemStatus: () => client.get("/system/status").then((r) => r.data.data),

  logs: (limit = 200, level) =>
    client
      .get("/logs", { params: { limit, level } })
      .then((r) => r.data.data),

  listUsers: () => client.get("/users").then((r) => r.data.data),

  createUser: (name, email, role) =>
    client.post("/users", { name, email, role }).then((r) => r.data.data),

  deleteUser: (userId) =>
    client.delete(`/users/${userId}`).then((r) => r.data.data),

  createBackup: () => client.post("/backup/create").then((r) => r.data.data),

  listBackups: () => client.get("/backup/list").then((r) => r.data.data),

  restoreBackup: (filename) =>
    client.post("/backup/restore", { filename }).then((r) => r.data.data),

  // Reports return a PDF binary directly (not the {success,data} JSON
  // envelope other endpoints use), so this bypasses the shared client
  // and triggers a real browser download via a Blob URL.
  downloadReport: async (start, end) => {
    const params = new URLSearchParams();
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    const response = await client.get(`/reports/generate?${params.toString()}`, {
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"] || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : "attendance_report.pdf";
    const url = window.URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    return { filename };
  },

  getAttentionWeights: () =>
    client.get("/settings/attention-weights").then((r) => r.data.data),

  updateAttentionWeights: (weights) =>
    client
      .put("/settings/attention-weights", { weights })
      .then((r) => r.data.data),
};

export default api;
