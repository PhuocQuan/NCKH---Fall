const SERVER_STORAGE_KEY = "nckh_server_url";
const TOKEN_STORAGE_KEY = "nckh_auth_token";
const USER_STORAGE_KEY = "nckh_auth_user";
const REMEMBER_KEY = "nckh_remember_user";
const SOUND_STORAGE_KEY = "nckh_sound_enabled";
const USER_META_KEY = "nckh_user_meta";
const ALERT_SOUND_URL = "sounds/fall_alert.wav";

const PATIENT_PROFILES = {
  default: { name: "Người được giám sát", initials: "HS", age: "Chưa nhập", room: "Chưa nhập", condition: "Mặc định", dob: "Chưa nhập", blood: "Chưa nhập", conditions: "Chưa nhập", contact: "Chưa nhập" },
  elderly: { name: "Người được giám sát", initials: "HS", age: "Chưa nhập", room: "Chưa nhập", condition: "Người già", dob: "Chưa nhập", blood: "Chưa nhập", conditions: "Chưa nhập", contact: "Chưa nhập" },
  child: { name: "Người được giám sát", initials: "HS", age: "Chưa nhập", room: "Chưa nhập", condition: "Trẻ em", dob: "Chưa nhập", blood: "Chưa nhập", conditions: "Chưa nhập", contact: "Chưa nhập" },
  pregnant: { name: "Người được giám sát", initials: "HS", age: "Chưa nhập", room: "Chưa nhập", condition: "Mang thai", dob: "Chưa nhập", blood: "Chưa nhập", conditions: "Chưa nhập", contact: "Chưa nhập" },
  disabled: { name: "Người được giám sát", initials: "HS", age: "Chưa nhập", room: "Chưa nhập", condition: "Khuyết tật", dob: "Chưa nhập", blood: "Chưa nhập", conditions: "Chưa nhập", contact: "Chưa nhập" },
};

const STATE_META = {
  alert: { label: "CẢNH BÁO", icon: "🚨", dot: "red", title: "Phát hiện té ngã — cảnh báo", desc: "Đã té ngã và nằm quá thời gian cho phép." },
  fallen: { label: "Đã té ngã", icon: "⬇️", dot: "red", title: "Phát hiện té ngã", desc: "Hệ thống xác nhận té ngã." },
  possible_fall: { label: "Nghi té ngã", icon: "⚠️", dot: "orange", title: "Nghi ngờ té ngã", desc: "Đang theo dõi thêm." },
  warning: { label: "Cảnh báo nhẹ", icon: "⚡", dot: "orange", title: "Tư thế bất thường", desc: "Chuyển động đáng chú ý." },
  lying: { label: "Đang nằm", icon: "🛏️", dot: "blue", title: "Đang nằm", desc: "Chưa xác định té ngã." },
  normal: { label: "Bình thường", icon: "✅", dot: "green", title: "Hoạt động bình thường", desc: "Không có dấu hiệu té ngã." },
};

const FALL_STATES = new Set(["possible_fall", "fallen", "alert", "warning"]);
const ALERT_STATES = new Set(["alert", "fallen", "possible_fall"]);
const ALARM_SOUND_STATES = new Set(["possible_fall", "fallen", "alert"]);
const PROGRESS_STATES = new Set(["POSSIBLE_FALL", "FALLEN", "ALERT", "possible_fall", "fallen", "alert"]);

const THUMB_GRADIENTS = [
  "linear-gradient(135deg,#475569,#1e293b)",
  "linear-gradient(135deg,#334155,#0f172a)",
  "linear-gradient(135deg,#3f3f46,#18181b)",
  "linear-gradient(135deg,#1e3a5f,#0f172a)",
];

let apiBase = "", authToken = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
let uiConfig = null, socket = null, alertAfterSeconds = 10, streamActive = false;
let toastTimer = null, allEvents = [], historyFilter = "all", splashDone = false;
let currentStatus = {}, lastEvent = null, emergencyDismissed = false;
let currentTab = "home", cameras = [], selectedCam = null;
let cameraFormMode = "add", cameraFormEditId = null, cameraFormSaving = false;
let managedUsers = [], userFormMode = "add", userFormEditUsername = null, userFormSaving = false;
let cloudProfileData = null, profileStats = null;
let audioCtx = null, alertAudio = null, lastAlarmState = "", alarmTicksSinceBeep = 3;

const $ = (id) => document.getElementById(id);

function txt(id, value) {
  const el = $(id);
  if (el && value !== undefined) el.textContent = value;
  return el;
}

function val(id, value) {
  const el = $(id);
  if (!el) return "";
  if (value !== undefined) el.value = value;
  return el.value;
}

function setHidden(id, hidden) {
  $(id)?.classList.toggle("hidden", hidden);
}

function setDisabled(id, disabled) {
  const el = $(id);
  if (el) el.disabled = disabled;
}

function loadSoundPreference() {
  const enabled = localStorage.getItem(SOUND_STORAGE_KEY) !== "0";
  if ($("toggleSound")) $("toggleSound").checked = enabled;
}

function saveSoundPreference() {
  localStorage.setItem(SOUND_STORAGE_KEY, $("toggleSound")?.checked ? "1" : "0");
}

function isSoundEnabled() {
  if ($("toggleSound")) return $("toggleSound").checked;
  return localStorage.getItem(SOUND_STORAGE_KEY) !== "0";
}

function ensureAudioContext() {
  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) audioCtx = new AC();
  }
  if (audioCtx?.state === "suspended") audioCtx.resume().catch(() => {});
}

function ensureAlertAudio() {
  if (!alertAudio) {
    alertAudio = new Audio(ALERT_SOUND_URL);
    alertAudio.preload = "auto";
  }
  return alertAudio;
}

function unlockAlertAudio() {
  ensureAudioContext();
  const audio = ensureAlertAudio();
  audio.load();
  const prevVolume = audio.volume;
  audio.volume = 0.001;
  const p = audio.play();
  if (p && typeof p.then === "function") {
    p.then(() => {
      audio.pause();
      audio.currentTime = 0;
      audio.volume = prevVolume;
    }).catch(() => {
      audio.volume = prevVolume;
    });
  } else {
    audio.volume = prevVolume;
  }
}

function playFallAlertSoundFallback() {
  ensureAudioContext();
  if (!audioCtx) return;
  try {
    const t = audioCtx.currentTime;
    [880, 880, 1100].forEach((freq, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "square";
      osc.frequency.value = freq;
      gain.gain.value = 0.22;
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      const start = t + i * 0.22;
      osc.start(start);
      osc.stop(start + 0.2);
    });
  } catch { /* trình duyệt chặn autoplay */ }
}

function playFallAlertSound() {
  if (!isSoundEnabled()) return;
  try {
    const audio = ensureAlertAudio();
    audio.currentTime = 0;
    const playPromise = audio.play();
    if (playPromise && typeof playPromise.catch === "function") {
      playPromise.catch(() => playFallAlertSoundFallback());
    }
  } catch {
    playFallAlertSoundFallback();
  }
  if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 350]);
}

function updateFallAlarm(state) {
  const s = (state || "normal").toLowerCase();
  if (!ALARM_SOUND_STATES.has(s)) {
    lastAlarmState = s;
    alarmTicksSinceBeep = 3;
    return;
  }
  if (!ALARM_SOUND_STATES.has(lastAlarmState)) {
    playFallAlertSound();
    alarmTicksSinceBeep = 0;
  } else {
    alarmTicksSinceBeep += 1;
    if (alarmTicksSinceBeep >= 2) {
      playFallAlertSound();
      alarmTicksSinceBeep = 0;
    }
  }
  lastAlarmState = s;
}

function resetFallAlarm() {
  lastAlarmState = "";
  alarmTicksSinceBeep = 3;
}

function isCapacitorApp() {
  return window.location.protocol === "capacitor:" || window.location.protocol === "file:" || window.location.hostname === "localhost";
}

function normalizeServerUrl(raw) {
  const v = (raw || "").trim();
  if (!v) return "";
  return (/^https?:\/\//i.test(v) ? v : `http://${v}`).replace(/\/+$/, "");
}

function resolveDefaultServer() {
  const saved = normalizeServerUrl(localStorage.getItem(SERVER_STORAGE_KEY));
  if (saved) return saved;
  return isCapacitorApp() ? "" : window.location.origin;
}

function authHeaders() {
  const h = { "Content-Type": "application/json" };
  if (authToken) h.Authorization = `Bearer ${authToken}`;
  return h;
}

function withTokenQuery(url) {
  if (!authToken) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(authToken)}`;
}

function showToast(msg, type = "info") {
  const t = $("toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  t.classList.remove("hidden");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 2800);
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Chào buổi sáng";
  if (h < 18) return "Chào buổi chiều";
  return "Chào buổi tối";
}

function capitalizeName(n) { return n ? n.charAt(0).toUpperCase() + n.slice(1) : "Admin"; }

function mapApiProfileToPatient(apiProfile) {
  if (!apiProfile) return null;
  return {
    name: apiProfile.full_name || "Người được giám sát",
    initials: apiProfile.initials || "HS",
    age: apiProfile.age_label || "Chưa nhập",
    room: apiProfile.room_label || "Chưa nhập",
    dob: apiProfile.date_of_birth || "Chưa nhập",
    blood: apiProfile.blood_type || "Chưa nhập",
    conditions: apiProfile.medical_conditions || "Chưa nhập",
    contact: apiProfile.emergency_contact || "Chưa nhập",
  };
}

function getPatient(profileId) {
  const key = profileId || "default";
  if (cloudProfileData) {
    return mapApiProfileToPatient(cloudProfileData) || PATIENT_PROFILES.default;
  }
  return PATIENT_PROFILES[key] || PATIENT_PROFILES.default;
}

function emptyIfMissing(value) {
  return ["Chưa nhập", "—"].includes(value || "") ? "" : (value || "");
}

function extractPhone(text) {
  const match = String(text || "").match(/(\+?\d[\d\s().-]{6,}\d)/);
  return match ? match[1].replace(/[^\d+]/g, "") : "";
}

function renderContactList() {
  const list = $("contactList");
  if (!list) return;
  const p = getPatient($("profileSelect")?.value || "default");
  const contact = emptyIfMissing(p.contact);
  list.innerHTML = "";
  if (!contact) {
    list.innerHTML = '<div class="activity-empty">Chưa nhập liên hệ khẩn cấp trong hồ sơ.</div>';
    return;
  }

  const phone = extractPhone(contact);
  const item = document.createElement("div");
  item.className = "contact-item";
  item.innerHTML = `<div class="contact-avatar">LH</div>
    <div class="contact-body"><p class="contact-name"></p><p class="contact-role">Liên hệ chính trong hồ sơ</p></div>
    <a class="contact-action call" aria-label="Gọi">📞</a>
    <a class="contact-action msg" aria-label="Nhắn tin">💬</a>`;
  item.querySelector(".contact-name").textContent = contact;
  const call = item.querySelector(".contact-action.call");
  const msg = item.querySelector(".contact-action.msg");
  if (phone) {
    call.href = `tel:${phone}`;
    msg.href = `sms:${phone}`;
  } else {
    call.classList.add("disabled");
    msg.classList.add("disabled");
  }
  list.appendChild(item);
}

function applyProfileStats(stats) {
  if (!stats) return;
  profileStats = stats;
  txt("healthFalls30", String(stats.falls_30_days ?? 0));
  txt("healthMobility", String(stats.mobility_score ?? 85));
  txt("healthActive", String(stats.active_hours_avg ?? 6.2));
}

async function loadPatientProfile(profileKey) {
  const key = profileKey || $("profileSelect")?.value || "default";
  try {
    const data = await api(`/api/patient-profile?profile=${encodeURIComponent(key)}`);
    cloudProfileData = data.profile || null;
    applyProfileStats(data.stats);
    const storage = data.storage === "database" ? "Supabase (cloud)" : "Máy chủ local";
    txt("profileStorage", storage);
    updatePatientCard(key);
    renderContactList();
    renderAssignedCams();
  } catch {
    txt("profileStorage", "—");
    updatePatientCard(key);
    renderContactList();
  }
}

function hideSplash(cb) {
  if (!splashDone) { splashDone = true; $("splashScreen").classList.add("hidden"); }
  if (cb) cb();
}

function loadUserMeta() {
  try { return JSON.parse(localStorage.getItem(USER_META_KEY) || "{}"); } catch { return {}; }
}

function saveUserMeta(meta) {
  localStorage.setItem(USER_META_KEY, JSON.stringify(meta));
}

function isAdminUser() {
  return Boolean(loadUserMeta().is_admin);
}

function setLoginConnStatus(kind, label) {
  const el = $("loginConnStatus");
  if (!el) return;
  el.textContent = label;
  el.className = `conn-status-pill ${kind === "ok" ? "ok" : kind === "err" ? "err" : "wait"}`;
}

async function testServerConnection() {
  const url = normalizeServerUrl($("loginServerInput").value || resolveDefaultServer());
  if (!url) throw new Error("Nhập địa chỉ server (IP laptop).");
  setLoginConnStatus("wait", "Đang kiểm tra...");
  $("loginConnDetail")?.classList.add("hidden");
  try {
    const res = await fetch(`${url}/api/health`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error("Server không phản hồi.");
    apiBase = url;
    localStorage.setItem(SERVER_STORAGE_KEY, apiBase);
    setLoginConnStatus("ok", "Đã kết nối");
    txt("loginConnDetail", `${data.service || "NCKH Fall Detection"} · phiên bản ${data.version || "?"} · Tài khoản do admin cấp`);
    $("loginConnDetail")?.classList.remove("hidden");
    return true;
  } catch (err) {
    setLoginConnStatus("err", "Lỗi kết nối");
    txt("loginConnDetail", err.message || "Không kết nối được. Kiểm tra WiFi, IP và server đang chạy.");
    $("loginConnDetail")?.classList.remove("hidden");
    return false;
  }
}

function openRequestAccessScreen() {
  $("loginScreen").classList.add("hidden");
  $("requestAccessScreen").classList.remove("hidden");
}

function closeRequestAccessScreen() {
  $("requestAccessScreen").classList.add("hidden");
  $("loginScreen").classList.remove("hidden");
}

async function submitAccessRequest(e) {
  e.preventDefault();
  const url = normalizeServerUrl($("loginServerInput").value || resolveDefaultServer());
  if (!url) throw new Error("Nhập địa chỉ server trước khi gửi yêu cầu.");
  const email = $("reqEmail").value.trim();
  const phone = $("reqPhone").value.trim();
  if (!email && !phone) throw new Error("Nhập email hoặc số điện thoại.");
  const body = {
    full_name: $("reqFullName").value.trim(),
    email,
    phone,
    role: $("reqRole").value,
    message: $("reqMessage").value.trim(),
  };
  const res = await fetch(`${url}/api/access-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const p = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(p.detail || "Gửi yêu cầu thất bại.");
  closeRequestAccessScreen();
  showToast(p.message || "Đã gửi yêu cầu. Admin sẽ liên hệ.", "success");
  $("accessRequestForm").reset();
}

const ROLE_LABELS = { caregiver: "Người chăm sóc", family: "Người thân", staff: "Nhân viên y tế" };
const STATUS_LABELS = { pending: "Chờ duyệt", approved: "Đã duyệt", rejected: "Từ chối" };

async function loadAccessRequests() {
  const payload = await api("/api/access-requests");
  renderAccessRequests(payload.requests || []);
}

function renderAccessRequests(requests) {
  const el = $("accessRequestList");
  if (!el) return;
  if (!requests.length) {
    el.innerHTML = '<div class="activity-empty">Chưa có yêu cầu truy cập</div>';
    return;
  }
  el.innerHTML = requests.map((req) => {
    const pending = req.status === "pending";
    const actions = pending ? `<div class="access-req-actions">
      <button type="button" class="btn btn-primary btn-sm" data-approve="${req.id}">Duyệt</button>
      <button type="button" class="btn btn-outline btn-sm" data-reject="${req.id}">Từ chối</button>
    </div>` : "";
    return `<article class="access-req-card ${pending ? "pending" : ""}">
      <p class="notif-title">${req.full_name} · ${ROLE_LABELS[req.role] || req.role}</p>
      <p class="notif-desc">${req.email || "—"} · ${req.phone || "—"}</p>
      <p class="notif-desc">${req.message || "Không có lời nhắn"}</p>
      <p class="notif-time">${STATUS_LABELS[req.status] || req.status} · ${formatDateTime(req.created_at)}</p>
      ${actions}
      ${pending ? '<p class="field-hint">Sau khi duyệt: vào Quản lý người dùng để tạo tài khoản.</p>' : ""}
    </article>`;
  }).join("");
  el.querySelectorAll("[data-approve]").forEach((btn) => {
    btn.addEventListener("click", () => reviewAccessRequest(btn.dataset.approve, "approved"));
  });
  el.querySelectorAll("[data-reject]").forEach((btn) => {
    btn.addEventListener("click", () => reviewAccessRequest(btn.dataset.reject, "rejected"));
  });
}

async function reviewAccessRequest(id, status) {
  const note = status === "approved"
    ? "Đã duyệt — cấp tài khoản qua auth.yaml"
    : prompt("Lý do từ chối (tùy chọn):") || "";
  await api(`/api/access-requests/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ status, review_note: note }),
  });
  showToast(status === "approved" ? "Đã đánh dấu duyệt" : "Đã từ chối", "success");
  await loadAccessRequests();
}

function updateRoleUi() {
  const admin = isAdminUser();
  $("gotoAccessRequestsBtn")?.classList.toggle("hidden", !admin);
  $("gotoUsersBtn")?.classList.toggle("hidden", !admin);
  $("addCameraBtn")?.classList.toggle("hidden", !admin);
  $("editCameraBtn")?.classList.toggle("hidden", !admin);
  if ($("gotoCamerasBtn")) {
    $("gotoCamerasBtn").textContent = admin ? "📹 Quản lý camera" : "📹 Xem camera";
  }
  if ($("camListHint")) {
    $("camListHint").textContent = admin
      ? "Chạm camera để xem live · bấm ✏️ để chỉnh sửa hoặc xóa"
      : "Chạm camera để xem live (camera do admin cấu hình)";
  }
}

async function refreshAuthMeta() {
  const me = await api("/api/auth/me");
  saveUserMeta({
    full_name: me.full_name,
    role: me.role,
    is_admin: Boolean(me.is_admin),
  });
  updateRoleUi();
  const roleLabel = me.is_admin ? "Quản trị viên" : (me.role || "caregiver");
  txt("profileAccount", `${me.full_name || me.username} (${roleLabel})`);
}

function showLogin(msg = "") {
  if (socket) { socket.close(); socket = null; }
  stopCameraStream();
  $("appShell").classList.add("hidden");
  $("mainTabbar").classList.add("hidden");
  $("requestAccessScreen").classList.add("hidden");
  hideSplash(() => $("loginScreen").classList.remove("hidden"));
  $("loginServerInput").value = resolveDefaultServer();
  const remembered = localStorage.getItem(REMEMBER_KEY);
  $("loginUserInput").value = remembered || localStorage.getItem(USER_STORAGE_KEY) || "admin";
  if (!isCapacitorApp() && resolveDefaultServer()) {
    $("loginConnHint").textContent = "Trên trình duyệt laptop: dùng địa chỉ hiện tại. Trên APK: nhập IP WiFi của laptop.";
  }
  setLoginConnStatus("", "Chưa kiểm tra");
  $("loginConnDetail")?.classList.add("hidden");
  $("loginError").classList.toggle("hidden", !msg);
  if (msg) $("loginError").textContent = msg;
}

function showApp() {
  const user = localStorage.getItem(USER_STORAGE_KEY) || "admin";
  const meta = loadUserMeta();
  hideSplash(() => {
    $("loginScreen").classList.add("hidden");
    $("requestAccessScreen").classList.add("hidden");
    $("appShell").classList.remove("hidden");
    $("mainTabbar").classList.remove("hidden");
  });
  $("headerUser").textContent = meta.full_name || capitalizeName(user);
  updateRoleUi();
  $("greetingText").textContent = getGreeting();
  $("serverUrlInput").value = apiBase;
  updateCsvLink();
  renderCamList();
  updatePatientCard($("profileSelect").value || "default");
}

function switchTab(tab) {
  currentTab = tab;
  if (!tab.startsWith("sub-")) {
    document.querySelectorAll(".tabbar-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  }
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  const el = $(`tab-${tab}`);
  if (el) el.classList.add("active");
  if (tab === "alerts") refreshEvents().catch(() => {});
  if (tab === "cameras") renderCamList();
  if (tab === "sub-access-requests") loadAccessRequests().catch((e) => showToast(e.message, "error"));
  if (tab === "sub-users") loadUsers().catch((e) => showToast(e.message, "error"));
}

function openSub(subId, hideTabbar = true) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  $(subId).classList.add("active");
  if (hideTabbar) $("mainTabbar").classList.add("hidden");
}

function closeSub(backTab) {
  $("mainTabbar").classList.remove("hidden");
  if (backTab === "users") {
    openSub("sub-users");
    loadUsers().catch((e) => showToast(e.message, "error"));
    return;
  }
  switchTab(backTab);
}

function setConnection(online = true) {
  const el = $("connectionState");
  el.textContent = online ? "● Online" : "● Offline";
  el.className = `conn-pill profile-conn ${online ? "online" : ""}`;
}

function ensureApiBase() { if (!apiBase) throw new Error("Chưa cấu hình máy chủ."); }
function ensureAuth() { if (!authToken) throw new Error("Chưa đăng nhập."); }

function handleUnauthorized() {
  authToken = "";
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  showLogin("Phiên hết hạn. Vui lòng đăng nhập lại.");
}

function getWsUrl() {
  const u = new URL(apiBase);
  return withTokenQuery(`${u.protocol === "https:" ? "wss:" : "ws:"}//${u.host}/ws/status`);
}

function normalizeStatusKey(d) { return (d.status || "READY").toUpperCase(); }

function helpForStatus(d) {
  if (d.state && uiConfig?.state_help?.[d.state]) return uiConfig.state_help[d.state];
  const k = normalizeStatusKey(d);
  return uiConfig?.system_help?.[k] || uiConfig?.state_help?.[d.state] || "";
}

function getStateMeta(state) {
  const k = (state || "normal").toLowerCase();
  return STATE_META[k] || { label: k, icon: "•", dot: "blue", title: k, desc: "" };
}

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }); } catch { return "—"; }
}

function formatDateTime(iso) {
  try { return new Date(iso).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }); } catch { return "—"; }
}

function formatLyingTime(sec) {
  const s = Math.floor(Number(sec) || 0);
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function isToday(iso) {
  try { return new Date(iso).toDateString() === new Date().toDateString(); } catch { return false; }
}

function isLast30Days(iso) {
  try { return (Date.now() - new Date(iso).getTime()) < 30 * 24 * 3600 * 1000; } catch { return false; }
}

function calcAiConfidence(ev) {
  if (!ev) return "—";
  const angle = parseFloat(ev.torso_angle_deg) || 0;
  const lying = parseFloat(ev.lying_seconds) || 0;
  const state = (ev.state || "").toLowerCase();
  let score = 50;
  if (state === "alert") score = 94;
  else if (state === "fallen") score = 85;
  else if (state === "possible_fall") score = 72;
  else if (state === "warning") score = 55;
  score += Math.min(10, angle / 10) + Math.min(5, lying);
  return `${Math.min(99, Math.round(score))}%`;
}

function findCamera(id) {
  return cameras.find((c) => c.id === id) || null;
}

function camDisplayName(cam) {
  if (!cam) return "—";
  return `${cam.id} · ${cam.name} · ${cam.room}`;
}

function camThumbStyle(index) {
  return THUMB_GRADIENTS[index % THUMB_GRADIENTS.length];
}

function pickDefaultCamera() {
  return cameras.find((c) => c.enabled) || cameras[0] || null;
}

function syncCameraDetail() {
  if (!selectedCam) return;
  txt("camDetailTitle", camDisplayName(selectedCam));
  txt("camSourceDisplay", selectedCam.source);
  txt("camIdDisplay", selectedCam.id);
  val("sourceInput", selectedCam.source);
}

function openCameraDetail(cam) {
  selectedCam = cam;
  syncCameraDetail();
  openSub("sub-camera");
  if (currentStatus.running && currentStatus.camera_id === cam.id) startCameraStream();
}

async function loadCameras() {
  const payload = await api("/api/cameras");
  cameras = payload.cameras || [];
  if (!selectedCam || !findCamera(selectedCam.id)) selectedCam = pickDefaultCamera();
  else selectedCam = findCamera(selectedCam.id);
  renderCamList();
  renderAssignedCams();
  syncCameraDetail();
}

function renderCamFormUserList(selected = []) {
  const selectedSet = new Set(selected);
  const users = managedUsers.filter((u) => !u.is_admin && u.enabled !== false);
  const box = $("camFormUserList");
  if (!box) return;
  if (!users.length) {
    box.innerHTML = '<p class="field-hint">Chưa có user. Thêm tại Quản lý người dùng.</p>';
    return;
  }
  box.innerHTML = users.map((u) => {
    const checked = selectedSet.has(u.username) ? "checked" : "";
    const label = u.full_name ? `${u.full_name} (@${u.username})` : u.username;
    return `<label class="check-row"><input type="checkbox" value="${u.username}" ${checked} /><span>${label}</span></label>`;
  }).join("");
}

function getCamFormAssignedUsers() {
  return [...($("camFormUserList")?.querySelectorAll('input[type="checkbox"]:checked') || [])].map((el) => el.value);
}

async function openCameraForm(mode, cam = null) {
  if (!isAdminUser()) {
    showToast("Chỉ admin mới được thêm hoặc sửa camera.", "error");
    return;
  }
  if (!managedUsers.length) {
    try { await loadUsers(); } catch { /* admin only */ }
  }
  cameraFormMode = mode;
  cameraFormEditId = cam?.id || null;
  txt("cameraFormTitle", mode === "add" ? "Thêm camera" : "Chỉnh sửa camera");
  $("deleteCameraBtn")?.classList.toggle("hidden", mode !== "edit");
  const idInput = $("camFormId");
  if (idInput) idInput.readOnly = mode === "edit";
  if (mode === "add") {
    const suggested = await api("/api/cameras/suggest-id");
    val("camFormId", suggested.id);
    val("camFormName", "");
    val("camFormRoom", "");
    val("camFormSource", "0");
    if ($("camFormEnabled")) $("camFormEnabled").checked = true;
    renderCamFormUserList([]);
  } else if (cam) {
    val("camFormId", cam.id);
    val("camFormName", cam.name);
    val("camFormRoom", cam.room);
    val("camFormSource", cam.source);
    if ($("camFormEnabled")) $("camFormEnabled").checked = Boolean(cam.enabled);
    renderCamFormUserList(cam.assigned_users || []);
  }
  openSub("sub-camera-form");
}

async function saveCameraFromForm(e) {
  e?.preventDefault?.();
  if (cameraFormSaving) return;
  cameraFormSaving = true;
  setDisabled("saveCameraBtn", true);
  setDisabled("deleteCameraBtn", true);
  $("cameraForm")?.setAttribute("aria-busy", "true");
  try {
    const body = {
      id: val("camFormId").trim().toUpperCase(),
      name: val("camFormName").trim(),
      room: val("camFormRoom").trim(),
      source: val("camFormSource").trim(),
      enabled: Boolean($("camFormEnabled")?.checked),
      assigned_users: getCamFormAssignedUsers(),
    };
    if (!body.name || !body.room || !body.source) throw new Error("Điền đủ thông tin camera.");
    if (!body.assigned_users.length) throw new Error("Chọn ít nhất một tài khoản được gán camera.");
    if (cameraFormMode === "add") {
      await api("/api/cameras", { method: "POST", body: JSON.stringify(body) });
      showToast("Đã thêm camera", "success");
    } else {
      await api(`/api/cameras/${encodeURIComponent(cameraFormEditId)}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      showToast("Đã cập nhật camera", "success");
    }
    await loadCameras();
    if (body.id) selectedCam = findCamera(body.id) || selectedCam;
    closeSub("cameras");
  } finally {
    cameraFormSaving = false;
    setDisabled("saveCameraBtn", false);
    setDisabled("deleteCameraBtn", false);
    $("cameraForm")?.removeAttribute("aria-busy");
  }
}

async function loadUsers() {
  const payload = await api("/api/users");
  managedUsers = payload.users || [];
  renderUserList();
}

function renderUserList() {
  const el = $("userList");
  if (!el) return;
  if (!managedUsers.length) {
    el.innerHTML = '<div class="activity-empty">Chưa có người dùng · nhấn + Thêm</div>';
    return;
  }
  el.innerHTML = managedUsers.map((user) => {
    const role = user.is_admin ? "Quản trị viên" : (ROLE_LABELS[user.role] || user.role);
    const status = user.enabled ? "Đang bật" : "Đã khóa";
    const actions = user.is_admin
      ? `<button type="button" class="btn btn-outline btn-sm" data-edit-user="${user.username}">✏️ Sửa</button>`
      : `<div class="user-row-actions">
          <button type="button" class="btn btn-outline btn-sm" data-edit-user="${user.username}">✏️ Sửa</button>
          <button type="button" class="btn btn-danger btn-sm" data-delete-user="${user.username}">Xóa</button>
        </div>`;
    return `<article class="access-req-card">
      <p class="notif-title">${user.full_name || user.username}${user.is_admin ? " · Admin" : ""}</p>
      <p class="notif-desc">${user.username} · ${role} · ${status}</p>
      ${actions}
    </article>`;
  }).join("");
  el.querySelectorAll("[data-edit-user]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const user = managedUsers.find((u) => u.username === btn.dataset.editUser);
      if (user) openUserForm("edit", user);
    });
  });
  el.querySelectorAll("[data-delete-user]").forEach((btn) => {
    btn.addEventListener("click", () => deleteUser(btn.dataset.deleteUser).catch((e) => showToast(e.message, "error")));
  });
}

function openUserForm(mode, user = null) {
  if (!isAdminUser()) {
    showToast("Chỉ admin mới quản lý người dùng.", "error");
    return;
  }
  userFormMode = mode;
  userFormEditUsername = user?.username || null;
  txt("userFormTitle", mode === "add" ? "Thêm người dùng" : "Chỉnh sửa tài khoản");
  $("deleteUserBtn")?.classList.toggle("hidden", mode !== "edit" || Boolean(user?.is_admin));
  const usernameInput = $("userFormUsername");
  if (usernameInput) usernameInput.readOnly = mode === "edit";
  if (mode === "add") {
    val("userFormUsername", "");
    val("userFormFullName", "");
    val("userFormPassword", "");
    val("userFormRole", "caregiver");
    if ($("userFormEnabled")) $("userFormEnabled").checked = true;
    txt("userFormPasswordHint", "Bắt buộc khi tạo mới");
    if ($("userFormPassword")) $("userFormPassword").required = true;
    if ($("userFormRole")) $("userFormRole").disabled = false;
  } else if (user) {
    val("userFormUsername", user.username);
    val("userFormFullName", user.full_name || "");
    val("userFormPassword", "");
    val("userFormRole", user.role || "caregiver");
    if ($("userFormEnabled")) $("userFormEnabled").checked = Boolean(user.enabled);
    txt("userFormPasswordHint", user.is_admin ? "Để trống nếu không đổi mật khẩu admin" : "Để trống nếu không đổi mật khẩu");
    if ($("userFormPassword")) $("userFormPassword").required = false;
    if ($("userFormRole")) $("userFormRole").disabled = Boolean(user.is_admin);
  }
  openSub("sub-user-form");
}

async function saveUserFromForm() {
  if (userFormSaving) return;
  userFormSaving = true;
  setDisabled("saveUserBtn", true);
  setDisabled("deleteUserBtn", true);
  try {
    const username = val("userFormUsername").trim();
    const fullName = val("userFormFullName").trim();
    const password = val("userFormPassword");
    const role = val("userFormRole");
    const enabled = Boolean($("userFormEnabled")?.checked);
    if (!username) throw new Error("Nhập tên đăng nhập.");
    if (userFormMode === "add") {
      if (!password) throw new Error("Nhập mật khẩu cho tài khoản mới.");
      await api("/api/users", {
        method: "POST",
        body: JSON.stringify({ username, password, full_name: fullName, role, enabled }),
      });
      showToast("Đã tạo tài khoản", "success");
    } else {
      const body = { full_name: fullName, enabled };
      if (password) body.password = password;
      if (!managedUsers.find((u) => u.username === userFormEditUsername)?.is_admin) body.role = role;
      await api(`/api/users/${encodeURIComponent(userFormEditUsername)}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      showToast("Đã cập nhật tài khoản", "success");
    }
    await loadUsers();
    closeSub("users");
  } finally {
    userFormSaving = false;
    setDisabled("saveUserBtn", false);
    setDisabled("deleteUserBtn", false);
  }
}

async function deleteUser(username) {
  if (!username || !confirm(`Xóa tài khoản ${username}?`)) return;
  await api(`/api/users/${encodeURIComponent(username)}`, { method: "DELETE" });
  showToast("Đã xóa tài khoản");
  userFormEditUsername = null;
  await loadUsers();
  closeSub("users");
}

async function deleteUserFromForm() {
  if (!userFormEditUsername) return;
  await deleteUser(userFormEditUsername);
}

async function deleteCameraFromForm() {
  if (!isAdminUser()) {
    showToast("Chỉ admin mới được xóa camera.", "error");
    return;
  }
  if (!cameraFormEditId) return;
  if (!confirm(`Xóa camera ${cameraFormEditId}?`)) return;
  await api(`/api/cameras/${encodeURIComponent(cameraFormEditId)}`, { method: "DELETE" });
  showToast("Đã xóa camera");
  cameraFormEditId = null;
  await loadCameras();
  selectedCam = pickDefaultCamera();
  closeSub("cameras");
}

function fillPatientProfileForm() {
  const p = cloudProfileData || {};
  const fallback = getPatient($("profileSelect")?.value || "default");
  val("patientFormFullName", emptyIfMissing(p.full_name || fallback.name));
  val("patientFormAge", emptyIfMissing(p.age_label || fallback.age));
  val("patientFormRoom", emptyIfMissing(p.room_label || fallback.room));
  val("patientFormDob", emptyIfMissing(p.date_of_birth || fallback.dob));
  val("patientFormBlood", emptyIfMissing(p.blood_type || fallback.blood));
  val("patientFormConditions", emptyIfMissing(p.medical_conditions || fallback.conditions));
  val("patientFormContact", emptyIfMissing(p.emergency_contact || fallback.contact));
}

function openPatientProfileForm() {
  fillPatientProfileForm();
  openSub("sub-profile-form");
}

async function savePatientProfile() {
  const key = $("profileSelect")?.value || "default";
  const payload = {
    full_name: val("patientFormFullName").trim(),
    age_label: val("patientFormAge").trim(),
    room_label: val("patientFormRoom").trim(),
    date_of_birth: val("patientFormDob").trim(),
    blood_type: val("patientFormBlood").trim(),
    medical_conditions: val("patientFormConditions").trim(),
    emergency_contact: val("patientFormContact").trim(),
  };
  const data = await api(`/api/patient-profile?profile=${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  cloudProfileData = data.profile || null;
  applyProfileStats(data.stats);
  txt("profileStorage", data.storage === "database" ? "Supabase (cloud)" : "Máy chủ local");
  updatePatientCard(key);
  renderContactList();
  closeSub("profile");
  showToast("Đã lưu hồ sơ cá nhân", "success");
}

function updatePatientCard(profileId) {
  const p = getPatient(profileId);
  txt("patientAvatar", p.initials);
  txt("patientName", p.name);
  txt("patientMeta", `${p.age || "Chưa nhập"} · ${p.room || "Chưa nhập"}`);
  txt("patientDob", p.dob || "—");
  txt("patientBlood", p.blood || "—");
  txt("patientConditions", p.conditions || "—");
  txt("patientContact", p.contact || "—");
  txt("emergencyPerson", p.name);
  renderContactList();
  if (profileStats) applyProfileStats(profileStats);
}

function updateEmergencyOverlay(data) {
  const state = (data.state || "").toLowerCase();
  if (state !== "alert" || emergencyDismissed) {
    $("emergencyOverlay").classList.add("hidden");
    return;
  }
  const p = getPatient(data.profile || $("profileSelect").value);
  const ai = calcAiConfidence(lastEvent || { state, lying_seconds: data.lying_seconds });
  $("emergencyLoc").textContent = selectedCam ? `${selectedCam.name} · ${selectedCam.room}` : "—";
  $("emergencyPerson").textContent = p.name;
  $("emergencyTime").textContent = lastEvent?.timestamp
    ? `Hôm nay, ${formatDateTime(lastEvent.timestamp)}`
    : `Hôm nay, ${new Date().toLocaleTimeString("vi-VN")}`;
  $("emergencyAi").textContent = ai;
  $("emergencyLying").textContent = formatLyingTime(data.lying_seconds);
  $("emergencyOverlay").classList.remove("hidden");
}

function updateBadges(events) {
  const alerts = events.filter((e) => (e.state || "").toLowerCase() === "alert").length;
  const fallsToday = events.filter((e) => FALL_STATES.has((e.state || "").toLowerCase()) && isToday(e.timestamp)).length;
  const falls30 = events.filter((e) => (e.state || "").toLowerCase() === "alert" && isLast30Days(e.timestamp)).length;

  txt("statFallsToday", String(fallsToday));
  txt("statActiveAlerts", String(alerts));
  txt("statProtected", "1");
  const enabledCount = cameras.filter((c) => c.enabled).length;
  txt("statCameras", currentStatus.running ? "1" : String(enabledCount));
  txt("healthFalls30", String(falls30));

  if (alerts > 0) {
    txt("notifBadge", String(alerts));
    $("notifBadge")?.classList.remove("hidden");
    txt("tabAlertBadge", String(alerts));
    $("tabAlertBadge")?.classList.remove("hidden");
  } else {
    $("notifBadge")?.classList.add("hidden");
    $("tabAlertBadge")?.classList.add("hidden");
  }
}

function renderActivityList(events) {
  const recent = [...events].reverse().slice(0, 4);
  if (!recent.length) {
    $("activityList").innerHTML = '<div class="activity-empty">Chưa có hoạt động</div>';
    return;
  }
  $("activityList").innerHTML = recent.map((ev) => {
    const m = getStateMeta(ev.state);
    return `<div class="activity-row">
      <span class="activity-dot ${m.dot}"></span>
      <div style="flex:1"><div class="activity-text">${m.title}</div><div class="activity-desc">${m.desc}</div></div>
      <span class="activity-time">${formatTime(ev.timestamp)}</span>
    </div>`;
  }).join("");
}

function filterEvents(events, filter) {
  if (filter === "all") return events;
  if (filter === "alert") return events.filter((e) => (e.state || "").toLowerCase() === "alert");
  if (filter === "warning") return events.filter((e) => (e.state || "").toLowerCase() === "warning");
  if (filter === "fall") return events.filter((e) => FALL_STATES.has((e.state || "").toLowerCase()));
  if (filter === "system") return events.filter((e) => (e.state || "").toLowerCase() === "normal");
  return events;
}

function notifSubtext(ev) {
  const state = (ev.state || "").toLowerCase();
  const ai = calcAiConfidence(ev);
  if (state === "alert" || state === "fallen") return `AI ${ai} · phản hồi ngay`;
  if (state === "warning" || state === "possible_fall") return `Nằm ${ev.lying_seconds || 0}s · theo dõi thêm`;
  if (state === "normal") return "Hệ thống hoạt động bình thường";
  return getStateMeta(ev.state).desc;
}

function renderNotifications(events) {
  const filtered = filterEvents(events, historyFilter);
  if (!filtered.length) {
    $("eventLog").innerHTML = '<div class="activity-empty">Chưa có thông báo</div>';
    return;
  }
  $("eventLog").innerHTML = [...filtered].reverse().map((ev) => {
    const m = getStateMeta(ev.state);
    const isAlert = (ev.state || "").toLowerCase() === "alert";
    const sub = notifSubtext(ev);
    return `<article class="notif-card${isAlert ? " alert-card" : ""}">
      <div class="notif-dot ${m.dot}">${m.icon}</div>
      <div class="notif-body"><p class="notif-title">${m.title}${selectedCam ? ` — ${selectedCam.room}` : ""}</p><p class="notif-desc">${sub}</p></div>
      <span class="notif-time">${formatTime(ev.timestamp)}</span>
    </article>`;
  }).join("");
}

function camStatusFor(cam) {
  const state = (currentStatus.state || "").toLowerCase();
  const isRunningThis = currentStatus.running && currentStatus.camera_id === cam.id;
  if (!cam.enabled) return { text: "Tắt", cls: "off", thumb: "" };
  if (!isRunningThis) return { text: "Sẵn sàng", cls: "off", thumb: "" };
  if (state === "alert" || state === "fallen") return { text: "Đã té ngã", cls: "danger", thumb: "danger" };
  if (state === "warning" || state === "possible_fall") return { text: "Cảnh báo", cls: "warn", thumb: "warn" };
  return { text: "Bình thường", cls: "ok", thumb: "ok" };
}

function renderCamList() {
  if (!cameras.length) {
    const emptyMsg = isAdminUser()
      ? "Chưa có camera · nhấn + Thêm"
      : "Chưa có camera · liên hệ admin để được gán";
    $("camList").innerHTML = `<div class="activity-empty">${emptyMsg}</div>`;
    return;
  }
  $("camList").innerHTML = cameras.map((cam, index) => {
    const st = camStatusFor(cam);
    const isLive = cam.enabled && currentStatus.running && streamActive && currentStatus.camera_id === cam.id;
    const liveBadge = isLive ? '<span class="cam-thumb-live"><span class="dot"></span>LIVE</span>' : "";
    const statusBadge = cam.enabled ? `<span class="cam-thumb-status ${st.thumb || st.cls}">${st.text}</span>` : '<span class="cam-thumb-status off" style="background:#64748b">Tắt</span>';
    const editBtn = isAdminUser()
      ? `<button type="button" class="cam-edit-btn" data-edit-cam="${cam.id}" aria-label="Chỉnh sửa">✏️</button>`
      : "";
    return `<div class="cam-list-item" data-cam="${cam.id}" role="button" tabindex="0">
        <div class="cam-list-thumb" style="background:${camThumbStyle(index)}">
          ${liveBadge}${statusBadge}
          ${!isLive ? '<span style="opacity:.35;font-size:2rem">📷</span>' : ""}
        </div>
        <div class="cam-list-footer">
          <span class="cam-list-dot ${st.cls}"></span>
          <span class="cam-list-name">${camDisplayName(cam)}</span>
          <span class="cam-list-actions">
            ${editBtn}
            <span class="cam-list-arrow">›</span>
          </span>
        </div>
      </div>`;
  }).join("");

  $("camList").querySelectorAll(".cam-list-item[data-cam]").forEach((row) => {
    row.addEventListener("click", (e) => {
      if (e.target.closest("[data-edit-cam]")) return;
      const cam = findCamera(row.dataset.cam);
      if (cam) openCameraDetail(cam);
    });
  });
  $("camList").querySelectorAll("[data-edit-cam]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const cam = findCamera(btn.dataset.editCam);
      if (cam) openCameraForm("edit", cam);
    });
  });
}

function renderAssignedCams() {
  $("assignedCamList").innerHTML = cameras.filter((c) => c.enabled).map((cam) => {
    const st = camStatusFor(cam);
    const bc = st.cls === "off" ? "ok" : st.cls;
    return `<div class="assigned-row"><span>${camDisplayName(cam)}</span><span class="assigned-badge ${bc}">● ${st.text}</span></div>`;
  }).join("");
}

function updateButtons(running) {
  setDisabled("startBtn", running);
  setDisabled("stopBtn", !running);
  setDisabled("resetBtn", !running);
  txt("startBtn", running ? "● Đang giám sát..." : "▶ Bắt đầu giám sát");
  setHidden("liveTag", !running);
}

function startCameraStream() {
  ensureApiBase(); ensureAuth();
  if (streamActive) return;
  $("streamImage").src = withTokenQuery(`${apiBase}/api/camera/stream.mjpg?ts=${Date.now()}`);
  $("streamImage").classList.remove("hidden");
  $("cameraPlaceholder").classList.add("hidden");
  streamActive = true;
}

function stopCameraStream() {
  streamActive = false;
  $("streamImage").removeAttribute("src");
  $("streamImage").classList.add("hidden");
  $("cameraPlaceholder").classList.remove("hidden");
  $("liveTag").classList.add("hidden");
}

function renderStatus(data) {
  currentStatus = data;
  const label = data.status_label || uiConfig?.status_display?.[normalizeStatusKey(data)] || data.status;
  const state = (data.state || "").toLowerCase();
  const meta = getStateMeta(state);

  txt("statusLabel", label);
  txt("stateHelp", helpForStatus(data));
  txt("statusDetail", `Profile: ${data.profile || "default"}`);

  const fps = data.fps ?? "—";
  const pose = data.pose_ms ?? "—";
  txt("metricsText", `${fps} fps · ${pose} ms`);
  txt("camDetailMeta", `${getPatient(data.profile).name} · Online · ${fps} fps`);

  txt("metricStatus", label);
  const metricStatus = $("metricStatus");
  if (metricStatus) metricStatus.className = ALERT_STATES.has(state) ? "danger" : "";
  txt("metricLying", data.lying_seconds != null ? formatLyingTime(data.lying_seconds) : "—");
  const metricLying = $("metricLying");
  if (metricLying) metricLying.className = data.lying_seconds > 0 ? "danger" : "";
  txt("metricTorso", lastEvent?.torso_angle_deg ? `${lastEvent.torso_angle_deg}°` : "—");
  txt("metricHip", lastEvent?.hip_velocity ? `${lastEvent.hip_velocity} m/s` : "—");
  txt("metricAi", calcAiConfidence(lastEvent || { state, lying_seconds: data.lying_seconds, torso_angle_deg: 0 }));
  const metricAi = $("metricAi");
  if (metricAi) metricAi.className = ALERT_STATES.has(state) ? "danger" : "";

  const tag = $("camStatusTag");
  if (tag) {
    tag.textContent = label;
    tag.className = "cam-status-tag";
    if (state === "alert" || state === "fallen") tag.classList.add("danger");
    else if (ALERT_STATES.has(state) || state === "warning") tag.classList.add("warn");
    else if (state === "normal") tag.classList.add("ok");
  }

  const ps = $("patientStatus");
  if (ps) {
    ps.textContent = `● ${label}`;
    ps.className = "patient-status";
    if (state === "alert" || state === "fallen") ps.classList.add("danger");
    else if (state === "warning" || state === "possible_fall") ps.classList.add("warn");
  }

  const isCritical = ALERT_STATES.has(state);
  setHidden("alertBanner", !isCritical);
  if (isCritical) {
    const lying = data.lying_seconds != null ? formatLyingTime(data.lying_seconds) : "—";
    txt("alertBannerTitle", `${meta.title} — ${selectedCam?.room || "—"}`);
    txt("alertBannerSub", `${getPatient(data.profile).name} · nằm ${lying} · AI ${calcAiConfidence(lastEvent || { state })}`);
  }

  updateButtons(Boolean(data.running) && data.camera_id === selectedCam?.id);
  if (data.running && data.camera_id === selectedCam?.id) startCameraStream();
  else stopCameraStream();
  updateEmergencyOverlay(data);
  renderAssignedCams();
  txt("statCameras", data.running ? "1" : String(cameras.filter((c) => c.enabled).length));
  if (data.camera_id) {
    const active = findCamera(data.camera_id);
    if (active) selectedCam = active;
    syncCameraDetail();
  }
  renderCamList();

  alertAfterSeconds = Number(data.alert_after_seconds) || alertAfterSeconds;
  const showProg = data.lying_seconds != null && PROGRESS_STATES.has(state);
  setHidden("progressWrap", !showProg);
  if (showProg) {
    const sec = Number(data.lying_seconds) || 0;
    const fill = $("progressFill");
    if (fill) fill.style.width = `${Math.min(100, (sec / alertAfterSeconds) * 100)}%`;
    txt("progressText", `Thời gian nằm: ${sec.toFixed(1)}s / ${alertAfterSeconds}s`);
  }
  updatePatientCard(data.profile || $("profileSelect").value);
  if (data.running) updateFallAlarm(state);
  else resetFallAlarm();
}

async function api(path, options = {}) {
  ensureApiBase(); ensureAuth();
  const res = await fetch(`${apiBase}${path}`, { headers: authHeaders(), ...options });
  if (res.status === 401) { handleUnauthorized(); throw new Error("Phiên hết hạn."); }
  if (!res.ok) { const p = await res.json().catch(() => ({})); throw new Error(p.detail || `Lỗi ${res.status}`); }
  return res.json();
}

async function refreshEvents() {
  const payload = await api("/api/events?limit=80");
  allEvents = payload.events || [];
  if (allEvents.length) lastEvent = allEvents[allEvents.length - 1];
  updateBadges(allEvents);
  renderActivityList(allEvents);
  renderNotifications(allEvents);
  if (currentStatus.state) renderStatus(currentStatus);
}

async function refreshStatus() {
  renderStatus(await api("/api/status"));
  setConnection(true);
}

async function loadUiConfig() {
  uiConfig = await api("/api/ui-config");
  $("profileSelect").innerHTML = "";
  for (const p of uiConfig.profiles || []) {
    const o = document.createElement("option");
    o.value = p.id;
    o.textContent = p.label || p.id;
    $("profileSelect").appendChild(o);
  }
}

async function loadSettings() {
  loadSoundPreference();
  const s = await api("/api/settings");
  $("profileSelect").value = s.profile;
  $("alertSecondsInput").value = s.alert_after_seconds;
  $("sensitivitySlider").value = s.alert_after_seconds;
  $("sliderValue").textContent = `Cân bằng (${s.alert_after_seconds}s)`;
  $("landmarksCheckbox").checked = s.draw_landmarks;
  $("snapshotCheckbox").checked = s.snapshot_on_alert;
  alertAfterSeconds = s.alert_after_seconds;
  updatePatientCard(s.profile);
}

async function saveSettings() {
  const sec = Number($("alertSecondsInput").value);
  await api("/api/settings", {
    method: "PUT",
    body: JSON.stringify({
      profile: $("profileSelect").value,
      alert_after_seconds: sec,
      draw_landmarks: $("landmarksCheckbox").checked,
      snapshot_on_alert: $("snapshotCheckbox").checked,
    }),
  });
  alertAfterSeconds = sec;
  updatePatientCard($("profileSelect").value);
  showToast("Đã lưu cài đặt", "success");
}

function updateCsvLink() { $("csvLink").href = withTokenQuery(`${apiBase}/api/events/csv`); }

async function saveServerAndReconnect() {
  const url = normalizeServerUrl($("serverUrlInput").value);
  if (!url) throw new Error("Nhập địa chỉ server.");
  apiBase = url;
  localStorage.setItem(SERVER_STORAGE_KEY, apiBase);
  updateCsvLink();
  if (socket) socket.close();
  await Promise.all([loadUiConfig(), loadSettings(), loadCameras()]);
  await refreshStatus();
  await refreshEvents();
  connectSocket();
  showToast("Đã kết nối lại", "success");
}

async function startMonitor() {
  if (!selectedCam) throw new Error("Chưa chọn camera.");
  if (!selectedCam.enabled) throw new Error("Camera đang tắt. Bật lại trong phần chỉnh sửa.");
  const payload = await api("/api/control/start", {
    method: "POST",
    body: JSON.stringify({ camera_id: selectedCam.id }),
  });
  emergencyDismissed = false;
  renderStatus({ ...payload.status, profile: $("profileSelect").value, alert_after_seconds: alertAfterSeconds });
  await refreshEvents();
  showToast("Đang giám sát", "success");
}

async function stopMonitor() {
  stopCameraStream();
  resetFallAlarm();
  renderStatus((await api("/api/control/stop", { method: "POST" })).status);
  $("emergencyOverlay").classList.add("hidden");
  showToast("Đã dừng");
}

async function resetMonitor() {
  emergencyDismissed = false;
  renderStatus((await api("/api/control/reset", { method: "POST" })).status);
  showToast("Đã reset");
}

function connectSocket() {
  if (!apiBase || !authToken) return;
  socket = new WebSocket(getWsUrl());
  socket.onopen = () => setConnection(true);
  socket.onmessage = (m) => {
    try {
      const d = JSON.parse(m.data);
      if (!d.profile) d.profile = $("profileSelect").value;
      renderStatus(d);
    } catch (e) { console.error(e); }
  };
  socket.onclose = () => { if (apiBase && authToken) { setConnection(false); setTimeout(connectSocket, 2000); } };
  socket.onerror = () => setConnection(false);
}

async function login(user, pass, server) {
  const url = normalizeServerUrl(server || resolveDefaultServer());
  if (!url) throw new Error("Nhập địa chỉ máy chủ.");
  if (!(await fetch(`${url}/api/health`)).ok) throw new Error("Không kết nối được máy chủ.");
  const res = await fetch(`${url}/api/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: user, password: pass }),
  });
  const p = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(p.detail || "Đăng nhập thất bại.");
  apiBase = url; authToken = p.token;
  localStorage.setItem(SERVER_STORAGE_KEY, apiBase);
  localStorage.setItem(TOKEN_STORAGE_KEY, authToken);
  localStorage.setItem(USER_STORAGE_KEY, user);
  saveUserMeta({
    full_name: p.full_name || user,
    role: p.role || "caregiver",
    is_admin: Boolean(p.is_admin),
  });
  updateRoleUi();
  unlockAlertAudio();
  if ($("rememberMe").checked) localStorage.setItem(REMEMBER_KEY, user);
  else localStorage.removeItem(REMEMBER_KEY);
}

async function logout() {
  try { if (apiBase && authToken) await fetch(`${apiBase}/api/auth/logout`, { method: "POST", headers: authHeaders() }); } catch { /* */ }
  authToken = "";
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_META_KEY);
  showLogin();
}

async function bootstrapApp() {
  showApp();
  updateCsvLink();
  unlockAlertAudio();
  await refreshAuthMeta();
  await Promise.all([loadUiConfig(), loadSettings(), loadCameras()]);
  await loadPatientProfile($("profileSelect")?.value || "default");
  await refreshStatus();
  await refreshEvents();
  connectSocket();
}

async function tryAutoLogin() {
  setTimeout(async () => {
    apiBase = resolveDefaultServer();
    if (!apiBase || !authToken) { showLogin(); return; }
    try {
      if (!(await fetch(`${apiBase}/api/auth/me`, { headers: { Authorization: `Bearer ${authToken}` } })).ok) {
        handleUnauthorized(); return;
      }
      await bootstrapApp();
    } catch { showLogin("Không kết nối được máy chủ."); }
  }, 1400);
}

/* Events */
document.querySelectorAll(".tabbar-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

document.querySelectorAll("[data-back]").forEach((btn) => {
  btn.addEventListener("click", () => closeSub(btn.dataset.back));
});

document.querySelectorAll("[data-goto]").forEach((btn) => {
  btn.addEventListener("click", () => openSub(btn.dataset.goto));
});

document.querySelectorAll(".pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    historyFilter = pill.dataset.filter;
    document.querySelectorAll(".pill").forEach((p) => p.classList.toggle("active", p === pill));
    renderNotifications(allEvents);
  });
});

$("togglePass")?.addEventListener("click", () => {
  const i = $("loginPassInput");
  i.type = i.type === "password" ? "text" : "password";
});

$("forgotPassBtn")?.addEventListener("click", () => {
  showToast("Liên hệ admin NCKH để đặt lại mật khẩu. Không tự đăng ký được.");
});
$("requestAccessBtn")?.addEventListener("click", () => openRequestAccessScreen());
$("requestAccessBack")?.addEventListener("click", () => closeRequestAccessScreen());
$("accessRequestForm")?.addEventListener("submit", (e) => {
  $("accessRequestError").classList.add("hidden");
  submitAccessRequest(e).catch((err) => {
    $("accessRequestError").textContent = err.message;
    $("accessRequestError").classList.remove("hidden");
  });
});
$("testConnBtn")?.addEventListener("click", () => testServerConnection().catch((e) => showToast(e.message, "error")));
$("gotoAccessRequestsBtn")?.addEventListener("click", () => openSub("sub-access-requests"));
$("gotoUsersBtn")?.addEventListener("click", () => openSub("sub-users"));
$("editPatientProfileBtn")?.addEventListener("click", () => openPatientProfileForm());
$("savePatientProfileBtn")?.addEventListener("click", () => savePatientProfile().catch((e) => showToast(e.message, "error")));
$("patientProfileForm")?.addEventListener("submit", (e) => e.preventDefault());
$("addUserBtn")?.addEventListener("click", () => openUserForm("add"));
$("saveUserBtn")?.addEventListener("click", () => saveUserFromForm().catch((e) => showToast(e.message, "error")));
$("deleteUserBtn")?.addEventListener("click", () => deleteUserFromForm().catch((e) => showToast(e.message, "error")));
$("userForm")?.addEventListener("submit", (e) => e.preventDefault());
$("faceIdBtn")?.addEventListener("click", () => showToast("Sinh trắc học chưa hỗ trợ trên bản demo"));

$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("loginBtn").disabled = true;
  $("loginError").classList.add("hidden");
  try {
    const user = $("loginUserInput").value.trim();
    const server = $("loginServerInput").value;
    if (!(await testServerConnection())) throw new Error("Kiểm tra kết nối server trước khi đăng nhập.");
    await login(user, $("loginPassInput").value, server);
    ensureAudioContext();
    await bootstrapApp();
    showToast(`Xin chào, ${capitalizeName(user)}!`, "success");
  } catch (err) {
    $("loginError").textContent = err.message;
    $("loginError").classList.remove("hidden");
  } finally { $("loginBtn").disabled = false; }
});

$("logoutBtn").addEventListener("click", () => logout());
$("startBtn").addEventListener("click", () => startMonitor().catch((e) => showToast(e.message, "error")));
$("stopBtn").addEventListener("click", () => stopMonitor().catch((e) => showToast(e.message, "error")));
$("resetBtn").addEventListener("click", () => resetMonitor().catch((e) => showToast(e.message, "error")));
$("refreshEventsBtn").addEventListener("click", () => refreshEvents().catch((e) => showToast(e.message, "error")));
$("saveSettingsBtn").addEventListener("click", () => saveSettings().catch((e) => showToast(e.message, "error")));
$("saveServerBtn").addEventListener("click", () => saveServerAndReconnect().catch((e) => showToast(e.message, "error")));
$("viewAllActivity")?.addEventListener("click", () => switchTab("alerts"));
$("notifBtn")?.addEventListener("click", () => switchTab("alerts"));
$("alertBanner")?.addEventListener("click", () => { openSub("sub-camera"); if (currentStatus.running) startCameraStream(); });

$("emergencyViewCam")?.addEventListener("click", () => { $("emergencyOverlay").classList.add("hidden"); openSub("sub-camera"); });
$("emergencyCallBtn")?.addEventListener("click", () => { openSub("sub-contacts"); $("emergencyOverlay").classList.add("hidden"); });
$("emergencyDismiss")?.addEventListener("click", () => { emergencyDismissed = true; $("emergencyOverlay").classList.add("hidden"); });

$("sensitivitySlider")?.addEventListener("input", (e) => {
  const v = e.target.value;
  $("alertSecondsInput").value = v;
  $("sliderValue").textContent = `Cân bằng (${v}s)`;
});

$("profileSelect")?.addEventListener("change", () => {
  loadPatientProfile($("profileSelect").value).catch(() => updatePatientCard($("profileSelect").value));
});
$("toggleSound")?.addEventListener("change", () => {
  saveSoundPreference();
  showToast($("toggleSound").checked ? "Đã bật âm thanh cảnh báo" : "Đã tắt âm thanh cảnh báo");
});
$("testSoundBtn")?.addEventListener("click", () => {
  const wasOff = !isSoundEnabled();
  if (wasOff) {
    if ($("toggleSound")) $("toggleSound").checked = true;
    saveSoundPreference();
  }
  unlockAlertAudio();
  playFallAlertSound();
  showToast(wasOff ? "Đã bật chuông và phát thử" : "Đang phát chuông cảnh báo");
});

$("addCameraBtn")?.addEventListener("click", () => openCameraForm("add").catch((e) => showToast(e.message, "error")));
$("editCameraBtn")?.addEventListener("click", () => {
  if (!selectedCam) return showToast("Chưa chọn camera", "error");
  openCameraForm("edit", selectedCam).catch((e) => showToast(e.message, "error"));
});
$("gotoCamerasBtn")?.addEventListener("click", () => switchTab("cameras"));
$("saveCameraBtn")?.addEventListener("click", () => saveCameraFromForm().catch((err) => showToast(err.message, "error")));
$("cameraForm")?.addEventListener("submit", (e) => e.preventDefault());
$("deleteCameraBtn")?.addEventListener("click", () => deleteCameraFromForm().catch((e) => showToast(e.message, "error")));

document.querySelectorAll(".seg").forEach((seg) => {
  seg.addEventListener("click", () => {
    document.querySelectorAll(".seg").forEach((s) => s.classList.toggle("active", s === seg));
    document.body.classList.toggle("theme-dark", seg.dataset.theme === "dark");
    showToast(`Giao diện: ${seg.textContent}`);
  });
});

tryAutoLogin();
