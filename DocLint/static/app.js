"use strict";
const $ = (id) => document.getElementById(id);
const state = {
  file: null,
  profiles: [],
  job: null,
  busy: false,
  poll: null,
  timer: null,
  planKey: null,
  locks: new Set(),
  pages: { original: 1, result: 1, review: 1 },
  failures: 0,
};
const maxSize = 15 * 1024 * 1024;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const roleNames = {
  body: "Thân bài",
  heading: "Tiêu đề",
  emphasis: "Đoạn nhấn mạnh",
  table: "Bảng",
  image: "Ảnh",
  caption: "Chú thích",
  list: "Danh sách Word",
  manual_list: "Danh sách gõ tay",
  protected: "Cấu trúc được bảo vệ",
  code: "Mã nguồn",
  quote: "Trích dẫn",
  reference: "Tài liệu tham khảo",
  empty: "Đoạn không có chữ",
  toc: "Mục lục",
};

function error(message = "") {
  $("error-box").textContent = message;
  $("error-box").hidden = !message;
}
function remember(id) {
  try {
    if (id) sessionStorage.setItem("doclint-job", id);
    else sessionStorage.removeItem("doclint-job");
  } catch {}
}
function remembered() {
  try {
    return sessionStorage.getItem("doclint-job");
  } catch {
    return null;
  }
}
async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const e = new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Yêu cầu chưa thành công (${response.status}). Kiểm tra lựa chọn hoặc thử lại.`,
    );
    e.status = response.status;
    throw e;
  }
  return response;
}
function buttons() {
  $("submit-button").disabled =
    state.busy || !state.file || !state.profiles.length;
  $("file-input").disabled = state.busy;
  $("remove-file").disabled = state.busy;
  $("format-button").disabled = state.busy || !state.job?.analysis;
  $("profile-select").disabled = state.busy || !state.profiles.length;
  $("review").classList.toggle("ui-busy", state.busy);
  $("lint-form").setAttribute("aria-busy", String(state.busy));
}
function step(which) {
  for (const name of ["upload", "review", "result"])
    $("step-" + name).classList.toggle("current", name === which);
}
function scrollTo(id) {
  $(id).scrollIntoView({ behavior: "smooth", block: "start" });
}
function fileSelected(file) {
  if (state.busy || !file) return;
  error();
  if (!/\.docx$/i.test(file.name)) {
    error("Chọn tệp .docx. Hãy lưu .doc hoặc .docm sang DOCX trước.");
    return;
  }
  if (!file.size || file.size > maxSize) {
    error("Tệp phải có dung lượng từ 1 byte đến 15 MB.");
    return;
  }
  state.file = file;
  $("filename").textContent = file.name;
  $("filesize").textContent = (file.size / 1024).toFixed(1) + " KB · DOCX";
  $("selected-file").hidden = false;
  $("drop-zone").hidden = true;
  buttons();
}
$("file-input").addEventListener("change", (e) =>
  fileSelected(e.target.files[0]),
);
$("remove-file").addEventListener("click", () => {
  state.file = null;
  $("file-input").value = "";
  $("selected-file").hidden = true;
  $("drop-zone").hidden = false;
  error();
  buttons();
  $("file-input").focus();
});
for (const name of ["dragenter", "dragover"])
  $("drop-zone").addEventListener(name, (e) => {
    e.preventDefault();
    $("drop-zone").classList.add("drag-over");
  });
for (const name of ["dragleave", "drop"])
  $("drop-zone").addEventListener(name, (e) => {
    e.preventDefault();
    $("drop-zone").classList.remove("drag-over");
  });
$("drop-zone").addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length !== 1) {
    error("Hãy xử lý từng tài liệu để duyệt kết quả riêng.");
    return;
  }
  fileSelected(e.dataTransfer.files[0]);
});
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => e.preventDefault());

function profileChanged() {
  const p = state.profiles.find((p) => p.id === $("profile-select").value);
  if (!p) return;
  $("profile-description").textContent = p.description;
  $("spec-font").textContent = p.font;
  $("spec-size").textContent = p.font_size;
  $("spec-spacing").textContent = p.line_spacing;
  $("spec-margins").textContent = p.margins;
}
$("profile-select").addEventListener("change", profileChanged);
$("mode-select").addEventListener("change", () => {
  $("mode-description").textContent =
    $("mode-select").value === "strict"
      ? "Chỉ sửa thuộc tính. Không xóa Space, Tab hoặc đoạn trống."
      : "Cho phép thay khoảng trắng đầu thân bài, Tab đầu khối chữ ký và chuỗi đoạn thật sự rỗng trước chương đã duyệt. Không cắt khoảng trắng trong nội dung.";
});
function isLocked(block) {
  const end =
    state.job?.analysis?.blocks.find((b) => b.id === $("cover-end").value)
      ?.position ?? -1;
  return (
    state.locks.has(block.id) ||
    ($("cover-select").value === "keep" && block.position <= end) ||
    ($("preserve-references").checked && block.region === "references") ||
    ($("preserve-appendices").checked && block.region === "appendices")
  );
}
function eligibleIds(group) {
  const end =
    state.job?.analysis?.blocks.find((b) => b.id === $("cover-end").value)
      ?.position ?? -1;
  return group.block_ids.filter((id) => {
    const b = state.job.analysis.blocks.find((b) => b.id === id);
    return b && b.position > end && !isLocked(b);
  });
}
function reviewGroups() {
  const p = state.reviewPlan || {};
  return [
    ...(p.heading_groups || []),
    ...(p.layout_groups || []),
    ...(p.table_groups || []),
    ...(p.caption_groups || []),
  ];
}
function refreshLocks() {
  const blocks = state.job?.analysis?.blocks || [];
  let questions = 0;
  for (const select of $("review").querySelectorAll("select[data-group]")) {
    const group = reviewGroups().find((g) => g.id === select.dataset.group);
    const active = group && eligibleIds(group).length > 0;
    const enabled =
      select.dataset.kind !== "layout" || $("mode-select").value === "layout";
    const tableEnabled =
      select.dataset.kind !== "table" || $("normalize-tables").checked;
    select.closest(".question-group").hidden =
      !active || !enabled || !tableEnabled;
    select.disabled = state.busy || !active || !enabled || !tableEnabled;
    if (active && enabled && tableEnabled) questions++;
  }
  for (const [card, containers] of [
    ["heading-questions-card", ["outline-list"]],
    ["layout-questions-card", ["layout-review"]],
    ["object-questions-card", ["table-review", "caption-review"]],
  ])
    $(card).hidden = !containers.some((id) =>
      [...$(id).children].some((row) => !row.hidden),
    );
  $("lock-count").textContent =
    blocks.filter(isLocked).length + " khối được giữ";
  $("review-summary").textContent = questions
    ? `${questions} nhóm chưa đủ căn cứ tự xử lý. Một lựa chọn áp dụng cho cả nhóm; mặc định giữ nguyên nếu bạn chưa chắc.`
    : "Không có phần nào cần bạn chọn lại. Chọn mẫu trình bày, bìa hoặc mục lục nếu cần rồi hoàn thiện tài liệu.";
  const end = $("cover-end").value;
  $("cover-plan-note").textContent = end
    ? $("cover-select").value === "keep"
      ? "Giữ phần bìa đã nhận diện. Chọn một mẫu nếu muốn dàn bìa thành trang riêng."
      : "Dàn phần thông tin bìa hiện có thành trang riêng; nội dung bắt đầu ở trang sau. Không thêm tên hoặc logo."
    : "Chưa nhận diện thông tin bìa để dàn lại. Hệ thống giữ nguyên tài liệu.";
  const p = state.reviewPlan;
  if (p) {
    const o = collectHeadingChoices();
    const known = new Set([
      ...blocks
        .filter(
          (b) =>
            b.role === "heading" &&
            b.certainty === "certain" &&
            b.position > (blocks.find((b) => b.id === end)?.position ?? -1),
        )
        .map((b) => b.id),
      ...Object.keys(o.headings),
    ]);
    const available = known.size > 0;
    $("automatic-summary").textContent =
      (known.size ? `${known.size} đề mục đã xác định. ` : "") +
      "Thân bài, bảng đơn giản và ảnh trong dòng dùng quy tắc an toàn; không cần chọn lại từng phần.";
    $("toc-select").options[1].disabled = !available;
    if (!available) $("toc-select").value = "keep";
    $("toc-region-note").textContent = !available
      ? "Xác nhận một nhóm đề mục ở trên để tạo mục lục."
      : "Mục lục bắt đầu trên trang riêng, tách bìa và nội dung. Nếu quá dài, mục lục tiếp tục sang trang kế tiếp.";
  }
}
for (const id of [
  "cover-end",
  "cover-select",
  "preserve-references",
  "preserve-appendices",
  "mode-select",
  "normalize-tables",
])
  $(id).addEventListener("change", refreshLocks);
function renderLocks() {
  const query = $("block-search").value.trim().toLocaleLowerCase("vi");
  if (!query) {
    $("block-locks").replaceChildren();
    $("lock-limit").textContent =
      "Nhập từ khóa khi cần giữ nguyên một vùng riêng; không cần chọn từng đoạn.";
    return;
  }
  const all = (state.job?.analysis?.blocks || []).filter((b) =>
    (b.id + " " + b.text).toLocaleLowerCase("vi").includes(query),
  );
  $("block-locks").replaceChildren(
    ...all.slice(0, 30).map((b) => {
      const label = document.createElement("label");
      label.className = "check-line";
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = state.locks.has(b.id);
      check.setAttribute("aria-label", "Giữ nguyên " + b.id);
      check.addEventListener("change", () => {
        if (check.checked) state.locks.add(b.id);
        else state.locks.delete(b.id);
        refreshLocks();
      });
      const text = document.createElement("span");
      text.textContent = b.text || "Đối tượng không có chữ";
      label.append(check, text);
      return label;
    }),
  );
  $("lock-limit").textContent =
    all.length > 30
      ? `Hiển thị 30/${all.length} kết quả. Nhập cụ thể hơn để thu hẹp.`
      : `${all.length} kết quả.`;
}
$("block-search").addEventListener("input", renderLocks);
function groupControl(group, kind, choices, value) {
  const row = document.createElement("div");
  row.className = "question-group";
  const info = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = `${group.label} · ${group.block_ids.length} dòng`;
  const examples = document.createElement("ul");
  examples.className = "question-examples";
  for (const id of group.block_ids.slice(0, 3)) {
    const b = state.job.analysis.blocks.find((b) => b.id === id);
    const item = document.createElement("li");
    item.textContent = b?.text || "Đối tượng trong tài liệu";
    examples.append(item);
  }
  if (group.block_ids.length > 3) {
    const more = document.createElement("li");
    more.textContent = `Và ${group.block_ids.length - 3} dòng cùng dạng`;
    examples.append(more);
  }
  const select = document.createElement("select");
  select.dataset.group = group.id;
  select.dataset.kind = kind;
  select.setAttribute("aria-label", group.label);
  for (const [v, label] of choices) select.add(new Option(label, v));
  if (value === "custom") {
    const option = new Option("Giữ lựa chọn riêng đã lưu", "custom");
    option.disabled = true;
    select.add(option);
  }
  select.value = value || "keep";
  select.addEventListener("change", refreshLocks);
  info.append(title, examples);
  row.append(info, select);
  return row;
}
function commonValue(values) {
  return values.every((v) => v === values[0]) ? values[0] : "custom";
}
function fallbackPlan(a) {
  const groups = new Map();
  for (const b of a.blocks.filter(
    (b) =>
      ["heading", "emphasis"].includes(b.role) && b.certainty !== "certain",
  )) {
    const level = b.level || 1;
    if (!groups.has(level))
      groups.set(level, {
        id: "heading-" + level,
        label: "Các dòng có thể là đề mục",
        level,
        block_ids: [],
      });
    groups.get(level).block_ids.push(b.id);
  }
  return {
    automatic_headings: {},
    heading_groups: [...groups.values()],
    layout_groups: [],
    table_groups: [],
    caption_groups: [],
    cover_candidates: a.cover_end ? [a.cover_end] : [],
    counts: {},
  };
}
function renderReview(meta) {
  const a = meta.analysis;
  if (!a) return;
  if (state.planKey === meta.id) {
    refreshLocks();
    return;
  }
  state.planKey = meta.id;
  state.reviewPlan = a.review_plan || fallbackPlan(a);
  const plan = state.reviewPlan,
    o = meta.options || {};
  state.locks = new Set(o.locked_blocks || []);
  $("analysis-summary").replaceChildren(
    ...[
      `${a.summary.paragraphs} đoạn`,
      `${a.summary.tables} bảng`,
      `${a.summary.images} ảnh`,
      `${a.summary.equations} công thức`,
    ].map((text) => {
      const span = document.createElement("span");
      span.textContent = text;
      return span;
    }),
  );
  $("automatic-list").replaceChildren(
    ...[
      "Giữ cấp của tiêu đề Word đã có; nhận các chuỗi đề mục đánh số nhất quán.",
      "Chuẩn hóa thân bài, bảng đơn giản và ảnh trong dòng theo mẫu.",
      "Tự gắn chú thích khi chỉ có một đối tượng liền kề phù hợp.",
      "Giữ vùng tham khảo, phụ lục, công thức, code và cấu trúc phức tạp theo phạm vi an toàn.",
    ].map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    }),
  );
  const candidates = [
    ...new Set([
      ...(plan.cover_candidates || []),
      ...(o.cover_end ? [o.cover_end] : []),
    ]),
  ];
  $("cover-end").replaceChildren(
    new Option("Không có phần bìa", ""),
    ...candidates.map((id) => {
      const b = a.blocks.find((b) => b.id === id);
      return new Option(
        (id === a.cover_end ? "Đề xuất: " : "Kết thúc sau: ") +
          (b?.text || "Thông tin bìa").slice(0, 70),
        id,
      );
    }),
  );
  $("cover-end").value = o.cover_end || a.cover_end || "";
  for (const option of $("cover-select").options)
    if (option.value !== "keep") option.disabled = !candidates.length;
  $("toc-select").replaceChildren(
    new Option(a.toc_region ? "Giữ mục lục hiện tại" : "Giữ hiện tại", "keep"),
    new Option(
      a.toc_region ? "Thay mục lục — trang riêng" : "Tạo mục lục — trang riêng",
      a.toc_region ? "replace" : "insert",
    ),
  );
  $("outline-list").replaceChildren(
    ...plan.heading_groups.map((g) =>
      groupControl(
        g,
        "heading",
        [
          ["keep", "Giữ cách trình bày hiện tại"],
          ["heading", `Dùng làm đề mục cấp ${g.level}`],
        ],
        commonValue(
          g.block_ids.map((id) =>
            o.heading_levels?.[id] ? "heading" : "keep",
          ),
        ),
      ),
    ),
  );
  $("heading-count").textContent = plan.heading_groups.length + " nhóm";
  $("layout-review").replaceChildren(
    ...plan.layout_groups.map((g) =>
      groupControl(
        g,
        "layout",
        [
          ["keep", "Giữ vị trí hiện tại"],
          ["body", "Căn thành đoạn thường"],
          ["center", "Căn giữa"],
          ["right_block", "Căn khối bên phải"],
        ],
        commonValue(
          g.block_ids.map((id) => o.layout_decisions?.[id] || "keep"),
        ),
      ),
    ),
  );
  $("table-review").replaceChildren(
    ...plan.table_groups.map((g) =>
      groupControl(
        g,
        "table",
        [
          ["keep", "Giữ hàng đầu như hiện tại"],
          ["header", "Dùng hàng đầu làm tiêu đề cột"],
        ],
        commonValue(
          g.block_ids.map((id) =>
            o.table_headers?.includes(id) ? "header" : "keep",
          ),
        ),
      ),
    ),
  );
  $("caption-review").replaceChildren(
    ...plan.caption_groups.map((g) =>
      groupControl(
        g,
        "caption",
        [
          ["keep", "Giữ, chưa gắn đối tượng"],
          ["previous", "Gắn với đối tượng phía trước"],
          ["next", "Gắn với đối tượng phía sau"],
        ],
        commonValue(
          g.members.map((m) =>
            o.caption_links?.[m.id] === m.previous
              ? "previous"
              : o.caption_links?.[m.id] === m.next
                ? "next"
                : "keep",
          ),
        ),
      ),
    ),
  );
  for (const [id, key] of [
    ["profile-select", "profile"],
    ["mode-select", "mode"],
    ["cover-select", "cover"],
    ["toc-select", "toc"],
  ])
    if (o[key] !== undefined) $(id).value = o[key];
  for (const [id, key] of [
    ["preserve-references", "preserve_references"],
    ["preserve-appendices", "preserve_appendices"],
    ["normalize-tables", "normalize_tables"],
    ["normalize-images", "normalize_images"],
    ["hide-first-page", "hide_first_page_number"],
  ])
    if (o[key] !== undefined) $(id).checked = o[key];
  if (o.page_numbers !== undefined)
    $("page-numbers").checked = o.page_numbers === "arabic";
  profileChanged();
  $("mode-select").dispatchEvent(new Event("change"));
  renderLocks();
  refreshLocks();
  $("original-review-note").textContent = meta.original_preview.available
    ? "Bản gốc được dựng bằng LibreOffice."
    : "Chưa có bản dựng: " + (meta.original_preview.reason || "");
  renderPage("review");
}
function collectHeadingChoices() {
  const plan = state.reviewPlan || {},
    options = state.job?.options || {};
  const headings = {
    ...(plan.automatic_headings || {}),
    ...(options.heading_levels || {}),
  };
  const preserved = new Set(options.preserved_candidates || []);
  for (const select of $("outline-list").querySelectorAll(
    "select[data-group]",
  )) {
    const group = plan.heading_groups.find(
      (g) => g.id === select.dataset.group,
    );
    for (const id of eligibleIds(group)) {
      if (select.value === "heading") {
        headings[id] = group.level;
        preserved.delete(id);
      } else if (select.value === "keep") {
        delete headings[id];
        preserved.add(id);
      }
    }
  }
  const end =
    state.job?.analysis?.blocks.find((b) => b.id === $("cover-end").value)
      ?.position ?? -1;
  for (const id of Object.keys(headings)) {
    const b = state.job?.analysis?.blocks.find((b) => b.id === id);
    if (!b || isLocked(b) || b.position <= end) delete headings[id];
  }
  return {
    headings,
    preserved: [...preserved].filter(
      (id) =>
        !headings[id] &&
        state.job.analysis.blocks.some(
          (b) => b.id === id && b.position > end && !isLocked(b),
        ),
    ),
  };
}
function collectOptions() {
  const p = state.reviewPlan,
    saved = state.job.options || {};
  const { headings, preserved } = collectHeadingChoices();
  const decisions = { ...(saved.layout_decisions || {}) },
    links = { ...(saved.caption_links || {}) },
    tables = new Set(saved.table_headers || []);
  for (const select of $("layout-review").querySelectorAll(
    "select[data-group]",
  )) {
    if (select.disabled || select.value === "custom") continue;
    const group = p.layout_groups.find((g) => g.id === select.dataset.group);
    for (const id of eligibleIds(group)) decisions[id] = select.value;
  }
  for (const select of $("table-review").querySelectorAll(
    "select[data-group]",
  )) {
    if (select.disabled || select.value === "custom") continue;
    const group = p.table_groups.find((g) => g.id === select.dataset.group);
    for (const id of eligibleIds(group)) {
      if (select.value === "header") tables.add(id);
      else tables.delete(id);
    }
  }
  for (const select of $("caption-review").querySelectorAll(
    "select[data-group]",
  )) {
    if (select.disabled || select.value === "custom") continue;
    const group = p.caption_groups.find((g) => g.id === select.dataset.group);
    for (const member of group.members.filter((m) =>
      eligibleIds(group).includes(m.id),
    )) {
      if (select.value === "keep") delete links[member.id];
      else links[member.id] = member[select.value];
    }
  }
  return {
    profile: $("profile-select").value,
    mode: $("mode-select").value,
    heading_levels: headings,
    preserved_candidates: preserved,
    layout_decisions: decisions,
    caption_links: links,
    table_headers: [...tables],
    locked_blocks: [...state.locks],
    preserve_cover: $("cover-select").value === "keep",
    cover: $("cover-select").value,
    cover_end: $("cover-end").value || null,
    preserve_references: $("preserve-references").checked,
    preserve_appendices: $("preserve-appendices").checked,
    toc: $("toc-select").value,
    page_numbers: $("page-numbers").checked ? "arabic" : "keep",
    hide_first_page_number: $("hide-first-page").checked,
    normalize_tables: $("normalize-tables").checked,
    normalize_images: $("normalize-images").checked,
  };
}

function expiry() {
  if (!state.job) return;
  const seconds = Math.max(
    0,
    Math.ceil((Date.parse(state.job.expires_at) - Date.now()) / 1000),
  );
  $("expiry-label").textContent = seconds
    ? `Còn ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} để dùng phiên`
    : "Phiên đã hết hạn";
  if (!seconds) {
    clearTimeout(state.poll);
    clearInterval(state.timer);
    $("download-button").disabled = true;
    $("format-button").disabled = true;
    error("Phiên đã hết hạn. Hãy xóa phiên và tải lại tài liệu nếu cần.");
  }
}
function startExpiry() {
  clearInterval(state.timer);
  expiry();
  state.timer = setInterval(expiry, 1000);
}
async function applyJob(meta) {
  state.job = meta;
  $("diagnostic-tools").hidden = !meta.diagnostic;
  remember(meta.id);
  $("upload-workspace").hidden = true;
  $("session-bar").hidden = false;
  $("session-name").textContent = meta.filename;
  const running = ["queued", "analyzing", "formatting"].includes(meta.status);
  state.busy = running;
  $("processing").hidden = !running;
  $("progress-stage").textContent = meta.stage;
  $("progress-detail").textContent =
    meta.status === "queued"
      ? `Có ${meta.queue_waiting ?? 0} công việc đang chờ; mỗi tài liệu được xử lý trong vùng riêng.`
      : "Tiến trình đang chạy cục bộ; không gửi tài liệu đến AI.";
  if (meta.analysis) renderReview(meta);
  if (running) {
    $("review").hidden = true;
    $("results").hidden = true;
    step(meta.analysis ? "review" : "upload");
  } else if (meta.status === "review") {
    $("review").hidden = false;
    $("results").hidden = true;
    step("review");
    if (meta.error) error(meta.error);
  } else if (["ready", "partial"].includes(meta.status)) {
    $("review").hidden = true;
    renderResult(meta);
    step("result");
  } else if (meta.status === "failed") {
    error(
      meta.error ||
        "Không xử lý được tệp này. Hãy xóa phiên và thử tài liệu khác.",
    );
    $("review").hidden = true;
    $("results").hidden = true;
  }
  buttons();
  startExpiry();
  if (running) schedulePoll(meta.id);
}
function schedulePoll(id) {
  clearTimeout(state.poll);
  state.poll = setTimeout(() => poll(id), 700);
}
async function poll(id) {
  try {
    const meta = await (await request("/api/v1/jobs/" + id)).json();
    if (state.job?.id !== id) return;
    state.failures = 0;
    await applyJob(meta);
  } catch (e) {
    if (state.job?.id !== id) return;
    if (e.status === 404) {
      reset();
      error(
        "Phiên không còn tồn tại hoặc đã hết hạn. Bạn có thể tải lại tài liệu.",
      );
      return;
    }
    state.failures++;
    error(
      "Kết nối gián đoạn. " +
        (state.failures < 10
          ? "Đang thử kết nối lại…"
          : "Hãy tải lại trang để tiếp tục phiên còn hạn."),
    );
    if (state.failures < 10) {
      clearTimeout(state.poll);
      state.poll = setTimeout(() => poll(id), 3000);
    }
  }
}
$("lint-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (state.busy || !state.file) return;
  state.busy = true;
  buttons();
  error();
  $("processing").hidden = false;
  $("progress-stage").textContent = "Đang tải và tiếp nhận bản thảo";
  try {
    const body = new FormData();
    body.append("file", state.file);
    const meta = await (
      await request("/api/v1/jobs", { method: "POST", body })
    ).json();
    await applyJob(meta);
    scrollTo("processing");
  } catch (e) {
    state.busy = false;
    $("processing").hidden = true;
    buttons();
    error(e.message);
  }
});
$("format-button").addEventListener("click", async () => {
  if (state.busy || !state.job) return;
  error();
  const options = collectOptions();
  state.busy = true;
  buttons();
  try {
    const meta = await (
      await request("/api/v1/jobs/" + state.job.id + "/format", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(options),
      })
    ).json();
    await applyJob(meta);
    scrollTo("processing");
  } catch (e) {
    state.busy = false;
    buttons();
    refreshLocks();
    error(e.message);
    scrollTo("error-box");
  }
});
function listEntry(title, count, description, page) {
  const li = document.createElement("li");
  const h = document.createElement("strong");
  h.textContent = title;
  li.append(h);
  if (count) {
    const b = document.createElement("span");
    b.className = "count-badge";
    b.textContent = String(count);
    li.append(b);
  }
  if (description) {
    const p = document.createElement("p");
    p.textContent = description;
    li.append(p);
  }
  if (page) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "page-jump";
    b.textContent = "Xem trang " + page;
    b.addEventListener("click", () => jump(page));
    li.append(b);
  }
  return li;
}
function renderResult(meta) {
  const r = meta.report;
  $("results").hidden = false;
  $("result-name").textContent =
    meta.filename +
    " · " +
    (state.profiles.find((p) => p.id === r.profile)?.name || r.profile);
  $("result-pages").textContent = r.preview.available
    ? r.preview.page_count + " trang"
    : "Chưa dựng PDF";
  $("document-stats").textContent =
    `${r.summary.paragraphs} đoạn · ${r.summary.tables} bảng · ${r.summary.images} ảnh · ${r.summary.equations} công thức`;
  $("change-count").textContent = String(r.summary.changed_items);
  $("warning-count").textContent = String(r.warnings.length);
  $("partial-note").hidden = meta.status !== "partial";
  $("partial-note").textContent =
    "Đã đối chiếu nội dung, nhưng một số bước xem trước hoặc mục lục chưa hoàn tất. Đọc cảnh báo và kiểm tra bằng Word; có thể quay lại đổi phương án.";
  $("changes-list").replaceChildren(
    ...(r.changes.length
      ? r.changes.map((c) => listEntry(c.title, c.count))
      : [
          listEntry(
            "Không cần thay đổi thêm trong phạm vi đã chọn",
            0,
            "Hệ thống không sửa để tăng số lượng thay đổi.",
          ),
        ]),
  );
  $("warnings-list").replaceChildren(
    ...(r.warnings.length
      ? r.warnings.map((w) =>
          listEntry(w.title, w.count, w.description, w.page),
        )
      : [
          listEntry(
            "Không phát hiện cảnh báo trong phạm vi kiểm tra",
            0,
            "Vẫn cần mở Word xem lần cuối trước khi nộp.",
          ),
        ]),
  );
  const names = {
    verified: "Đã kiểm tra",
    partial: "Chưa đủ dữ kiện",
    unavailable: "Chưa thực hiện",
    not_requested: "Không yêu cầu",
    unresolved: "Chưa xác minh",
    needs_word_update: "Cần cập nhật Word",
  };
  $("checks-list").replaceChildren(
    ...r.checks.map((c) => {
      const n = document.createElement("span");
      n.className =
        "check-pill" +
        (!["verified", "not_requested"].includes(c.status) ? " pending" : "");
      n.textContent = c.title + " · " + (names[c.status] || c.status);
      return n;
    }),
  );
  $("jump-page").replaceChildren(new Option("Chọn trang…", ""));
  const pages = new Set([
    ...(r.changed_pages || []),
    ...r.warnings.filter((w) => w.page).map((w) => w.page),
  ]);
  for (const p of [...pages].sort((a, b) => a - b))
    $("jump-page").add(
      new Option(
        `Trang ${p}` +
          (r.changed_pages.includes(p)
            ? " · có thay đổi được định vị"
            : " · cần xem lại"),
        String(p),
      ),
    );
  $("download-button").disabled = false;
  $("report-button").disabled = false;
  $("pdf-button").disabled = !r.preview.available;
  state.pages.original = 1;
  state.pages.result = 1;
  renderPage("original");
  renderPage("result");
}
function renderPage(side) {
  const meta = state.job;
  if (!meta) return;
  const variant = side === "review" ? "original" : side;
  const info =
    variant === "original" ? meta.original_preview : meta.report?.preview;
  const image = $(
    side === "review" ? "review-original-image" : side + "-image",
  );
  const label = $(side === "review" ? "review-page-label" : side + "-label");
  const note = $(side === "review" ? "original-review-note" : side + "-note");
  const prev = $(side === "review" ? "review-prev" : side + "-prev");
  const next = $(side === "review" ? "review-next" : side + "-next");
  const total = info?.available ? info.page_count : 0;
  state.pages[side] = Math.min(Math.max(1, state.pages[side]), total || 1);
  image.hidden = !total;
  prev.disabled = !total || state.pages[side] <= 1;
  next.disabled = !total || state.pages[side] >= total;
  label.textContent = total
    ? `${state.pages[side]} / ${total}`
    : "Chưa có bản dựng";
  if (!total) {
    image.removeAttribute("src");
    note.textContent = info?.reason || "Chưa có PDF để xem.";
    return;
  }
  note.textContent = "";
  image.alt = `${variant === "original" ? "Bản gốc" : "Bản đã chuẩn hóa"}, trang ${state.pages[side]}`;
  image.onerror = () => {
    if (state.job?.id === meta.id)
      note.textContent =
        "Không tải được ảnh trang. Thử chuyển trang hoặc tải PDF.";
  };
  image.src = `/api/v1/jobs/${meta.id}/pages/${variant}/${state.pages[side]}.png?v=${meta.revision}`;
}
function movePage(side, delta) {
  state.pages[side] += delta;
  renderPage(side);
  if (side !== "review" && $("sync-pages").checked) {
    const other = side === "original" ? "result" : "original";
    state.pages[other] = state.pages[side];
    renderPage(other);
  }
}
for (const side of ["review", "original", "result"])
  for (const [name, delta] of [
    ["prev", -1],
    ["next", 1],
  ])
    $(side + "-" + name).addEventListener("click", () => movePage(side, delta));
function jump(page) {
  state.pages.result = page;
  renderPage("result");
  if ($("sync-pages").checked) {
    state.pages.original = page;
    renderPage("original");
  }
  scrollTo("result-image");
}
$("jump-page").addEventListener("change", () => {
  if ($("jump-page").value) jump(Number($("jump-page").value));
});
$("revise-button").addEventListener("click", () => {
  $("results").hidden = true;
  $("review").hidden = false;
  step("review");
  refreshLocks();
  scrollTo("review");
});
async function download(kind, button) {
  if (!state.job) return;
  button.disabled = true;
  error();
  const meta = state.job;
  const url = {
    word: meta.urls.download,
    pdf: meta.urls.result_pdf,
    report: meta.urls.report,
    diagnostic: meta.urls.diagnostic,
  }[kind];
  try {
    const blob = await (await request(url)).blob();
    const link = document.createElement("a");
    const object = URL.createObjectURL(blob);
    link.href = object;
    link.download =
      kind === "word"
        ? meta.filename.replace(/\.docx$/i, "_doclint.docx")
        : kind === "pdf"
          ? "doclint-result.pdf"
          : kind === "diagnostic"
            ? "doclint-diagnostic.json"
            : "doclint-report.json";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(object), 30000);
  } catch (e) {
    error(e.message);
    scrollTo("error-box");
  } finally {
    button.disabled = false;
    expiry();
  }
}
$("download-button").addEventListener("click", () =>
  download("word", $("download-button")),
);
$("pdf-button").addEventListener("click", () =>
  download("pdf", $("pdf-button")),
);
$("report-button").addEventListener("click", () =>
  download("report", $("report-button")),
);
$("diagnostic-button").addEventListener("click", () =>
  download("diagnostic", $("diagnostic-button")),
);
function reset() {
  state.reviewPlan = null;
  $("diagnostic-tools").hidden = true;
  clearTimeout(state.poll);
  clearInterval(state.timer);
  remember(null);
  state.job = null;
  state.file = null;
  state.planKey = null;
  state.locks.clear();
  state.busy = false;
  state.failures = 0;
  $("file-input").value = "";
  for (const id of [
    "review",
    "results",
    "processing",
    "session-bar",
    "selected-file",
  ])
    $(id).hidden = true;
  $("upload-workspace").hidden = false;
  $("drop-zone").hidden = false;
  step("upload");
  buttons();
}
async function deleteJob() {
  if (!state.job) return;
  const id = state.job.id;
  clearTimeout(state.poll);
  $("delete-session").disabled = true;
  $("cancel-job").disabled = true;
  error();
  try {
    let response;
    do {
      response = await request("/api/v1/jobs/" + id, { method: "DELETE" });
      if (response.status === 202) {
        $("processing").hidden = false;
        $("progress-stage").textContent = "Đang dừng xử lý và xóa dữ liệu";
        await sleep(400);
      }
    } while (response.status === 202);
    reset();
    error("Đã xóa phiên trên máy chủ. Bạn có thể chọn bản thảo khác.");
    scrollTo("upload-workspace");
  } catch (e) {
    error(
      "Chưa xác nhận xóa được phiên. Hãy thử lại; thời hạn vẫn được giữ nguyên.",
    );
  } finally {
    $("delete-session").disabled = false;
    $("cancel-job").disabled = false;
  }
}
$("delete-session").addEventListener("click", deleteJob);
$("cancel-job").addEventListener("click", deleteJob);
async function init() {
  try {
    const [profiles, cap] = await Promise.all([
      request("/api/v1/profiles").then((r) => r.json()),
      request("/api/v1/capabilities").then((r) => r.json()),
    ]);
    state.profiles = profiles;
    $("profile-select").replaceChildren(
      ...profiles.map((p) => new Option(p.name, p.id)),
    );
    profileChanged();
    $("capability-note").textContent =
      cap.message + " Giới hạn bản dựng: " + cap.max_pages + " trang.";
    buttons();
    const id = remembered();
    if (id) {
      try {
        await applyJob(await (await request("/api/v1/jobs/" + id)).json());
      } catch (e) {
        remember(null);
        if (e.status !== 404)
          error("Chưa nối lại được phiên. Tải lại trang nếu phiên còn hạn.");
      }
    }
  } catch (e) {
    error("Chưa kết nối được máy chủ. Giữ Terminal chạy và tải lại trang.");
  }
}
init();
