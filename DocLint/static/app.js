"use strict";
const $ = (id) => document.getElementById(id);
const state = {
  file: null,
  profiles: [],
  session: null,
  busy: false,
  downloading: false,
  timer: null,
};
const maxSize = 15 * 1024 * 1024;

function error(message) {
  $("error-box").textContent = message;
  $("error-box").hidden = !message;
}
function updateButtons() {
  $("submit-button").disabled =
    state.busy || state.downloading || !state.file || !state.profiles.length;
  $("file-input").disabled = state.busy || state.downloading;
  $("profile-select").disabled = state.busy || !state.profiles.length;
  $("remove-file").disabled = state.busy;
  $("lint-form").setAttribute("aria-busy", String(state.busy));
}
async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Yêu cầu chưa thành công (${response.status}). Vui lòng thử lại.`,
    );
  }
  return response;
}
function renderProfile() {
  const p = state.profiles.find(
    (item) => item.id === $("profile-select").value,
  );
  if (!p) return;
  $("profile-description").textContent = p.description;
  $("spec-font").textContent = p.font;
  $("spec-size").textContent = p.font_size;
  $("spec-spacing").textContent = p.line_spacing;
  $("spec-margins").textContent = p.margins;
}
async function loadProfiles() {
  try {
    state.profiles = await (await request("/api/v1/profiles")).json();
    $("profile-select").replaceChildren(
      ...state.profiles.map((p) => new Option(p.name, p.id)),
    );
    renderProfile();
  } catch (e) {
    error("Không tải được mẫu định dạng. Kiểm tra kết nối và tải lại trang.");
    $("profile-select").replaceChildren(new Option("Chưa tải được mẫu", ""));
  }
  updateButtons();
}
function selectFile(file) {
  if (state.busy) return;
  error("");
  if (!file) return;
  if (!/\.docx$/i.test(file.name)) {
    error(
      "Vui lòng chọn tệp .docx. Với tệp .doc hoặc .docm, hãy mở trong Word và lưu thành DOCX.",
    );
    return;
  }
  if (!file.size || file.size > maxSize) {
    error("Tệp phải có dung lượng từ 1 byte đến 15 MB.");
    return;
  }
  state.file = file;
  $("filename").textContent = file.name;
  $("filesize").textContent =
    file.size < 1024 * 1024
      ? `${(file.size / 1024).toFixed(1)} KB · DOCX`
      : `${(file.size / 1024 / 1024).toFixed(2)} MB · DOCX`;
  $("selected-file").hidden = false;
  $("drop-zone").hidden = true;
  updateButtons();
}
$("file-input").addEventListener("change", (event) =>
  selectFile(event.target.files[0]),
);
$("remove-file").addEventListener("click", () => {
  state.file = null;
  $("file-input").value = "";
  $("selected-file").hidden = true;
  $("drop-zone").hidden = false;
  error("");
  updateButtons();
  $("file-input").focus();
});
const zone = $("drop-zone");
for (const name of ["dragenter", "dragover"]) {
  zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.add("drag-over");
  });
}
for (const name of ["dragleave", "drop"]) {
  zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.remove("drag-over");
  });
}
zone.addEventListener("drop", (event) => {
  if (event.dataTransfer.files.length !== 1) {
    error("Hãy chọn từng tài liệu để xem và tải kết quả riêng.");
    return;
  }
  selectFile(event.dataTransfer.files[0]);
});
// Prevent dropping a document elsewhere from navigating away from the app.
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());
$("profile-select").addEventListener("change", renderProfile);

function listEntry(title, count, description) {
  const li = document.createElement("li");
  const heading = document.createElement("strong");
  heading.textContent = title;
  li.append(heading);
  if (count) {
    const badge = document.createElement("span");
    badge.className = "count-badge";
    badge.textContent = String(count);
    li.append(badge);
  }
  if (description) {
    const p = document.createElement("p");
    p.textContent = description;
    li.append(p);
  }
  return li;
}
function expiry() {
  if (!state.session) return;
  const seconds = Math.max(
    0,
    Math.ceil((Date.parse(state.session.expires_at) - Date.now()) / 1000),
  );
  if (!seconds) {
    $("expiry-label").textContent =
      "Phiên đã hết hạn. Hãy xử lý lại tài liệu nếu cần tải thêm.";
    $("download-button").disabled = true;
    clearInterval(state.timer);
  } else {
    $("expiry-label").textContent =
      `Còn ${Math.floor(seconds / 60)} phút ${String(seconds % 60).padStart(2, "0")} giây để tải kết quả.`;
  }
}
function renderResult(report, originalName) {
  state.session = report;
  $("result-name").textContent = originalName;
  $("score-before").textContent = `${report.score.before}%`;
  $("score-after").textContent = `${report.score.after}%`;
  $("score-scope").textContent = report.score.scope;
  $("change-count").textContent = String(report.summary.changed_properties);
  $("warning-count").textContent = String(report.warnings.length);
  $("document-stats").textContent =
    `${report.summary.paragraphs} đoạn · ${report.summary.tables} bảng · ${report.summary.images} ảnh · ${report.summary.equations} công thức`;
  $("changes-list").replaceChildren(
    ...(report.changes.length
      ? report.changes.map((item) => listEntry(item.title, item.count))
      : [
          listEntry(
            "Các mục kiểm tra đã khớp mẫu",
            0,
            "Không cần thay đổi thêm thuộc tính trong phạm vi tự động chuẩn hóa.",
          ),
        ]),
  );
  $("warnings-list").replaceChildren(
    ...(report.warnings.length
      ? report.warnings.map((item) =>
          listEntry(item.title, item.count, item.description),
        )
      : [
          listEntry(
            "Không phát hiện cảnh báo trong phạm vi kiểm tra",
            0,
            "Bạn vẫn nên mở tệp bằng Word để xem lại vị trí ngắt trang.",
          ),
        ]),
  );
  $("results").hidden = false;
  $("download-button").disabled = false;
  $("delete-session").disabled = false;
  expiry();
  clearInterval(state.timer);
  state.timer = setInterval(expiry, 1000);
  $("results").focus();
  $("results").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function deleteCurrent() {
  if (!state.session) return;
  await request(`/api/v1/sessions/${state.session.session_id}`, {
    method: "DELETE",
  });
  state.session = null;
  clearInterval(state.timer);
}
$("lint-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || !state.file) return;
  state.busy = true;
  updateButtons();
  error("");
  $("processing").hidden = false;
  const originalName = state.file.name;
  try {
    await deleteCurrent();
    $("results").hidden = true;
    const data = new FormData();
    data.append("file", state.file);
    data.append("profile", $("profile-select").value);
    const report = await (
      await request("/api/v1/lint", { method: "POST", body: data })
    ).json();
    renderResult(report, originalName);
  } catch (e) {
    error(
      e instanceof TypeError
        ? "Mất kết nối đến máy chủ. Kiểm tra mạng rồi thử lại; tệp gốc của bạn vẫn nguyên vẹn."
        : e.message,
    );
    $("error-box").scrollIntoView({ behavior: "smooth", block: "center" });
  } finally {
    state.busy = false;
    $("processing").hidden = true;
    updateButtons();
  }
});
$("download-button").addEventListener("click", async () => {
  if (!state.session) return;
  const session = state.session;
  state.downloading = true;
  updateButtons();
  $("delete-session").disabled = true;
  $("download-button").disabled = true;
  try {
    const response = await request(session.download_url);
    const blob = await response.blob();
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = session.filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    error("");
  } catch (e) {
    error(e.message || "Không tải được tệp. Vui lòng thử lại.");
    $("error-box").scrollIntoView({ behavior: "smooth", block: "center" });
  } finally {
    state.downloading = false;
    updateButtons();
    if (state.session === session) {
      $("delete-session").disabled = false;
      $("download-button").disabled = false;
      expiry();
    }
  }
});
$("delete-session").addEventListener("click", async () => {
  $("delete-session").disabled = true;
  try {
    await deleteCurrent();
    $("expiry-label").textContent =
      "Đã xóa tệp kết quả và báo cáo trên máy chủ.";
    $("download-button").disabled = true;
    error("");
  } catch (e) {
    error(
      "Chưa xóa được kết quả. Bạn có thể thử lại; phiên vẫn tự hết hạn sau 30 phút.",
    );
    $("delete-session").disabled = false;
  }
});
loadProfiles();
