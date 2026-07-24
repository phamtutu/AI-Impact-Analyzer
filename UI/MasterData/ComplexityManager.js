const API = "http://127.0.0.1:8000/api/v1/complexities";

const state = {
  editingId: null,
  editingDisplayOrder: 0,
  options: null,
};

const $ = (id) => document.getElementById(id);

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch (_) {}
    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>'"]/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
      }[character])
  );
}

function fillOptions(select, values, includeAll = false) {
  select.innerHTML = includeAll ? '<option value="">Tất cả</option>' : "";
  values.forEach((value) => select.add(new Option(value, value)));
}

async function loadOptions() {
  state.options = await request(`${API}/options`);
  fillOptions($("complexityProcessType"), state.options.process_types);
}

async function loadComplexities() {
  try {
    const data = await request(API);
    $("complexityCount").textContent = data.total;
    renderTable(data.items);
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderTable(items) {
  const body = $("complexityBody");

  if (!items.length) {
    body.innerHTML = `
            <div class="empty">
                <div class="glyph">— · · —</div>
                Chưa có dữ liệu độ phức tạp.
            </div>`;
    return;
  }

  const rows = items
    .map((item) => {
      const encoded = encodeURIComponent(JSON.stringify(item));
      const complexityCells = [1, 2, 3, 4, 5]
        .map(
          (index) =>
            `<td class="complexity-cell">${escapeHtml(
              item[`c${index}_description`]
            )}</td>`
        )
        .join("");

      return `
            <tr>
                <td><span class="tag ${
                  item.process_type === "Batch" ? "tag-amber" : "tag-blue"
                }">${escapeHtml(item.process_type)}</span></td>
                <td>${escapeHtml(item.item_name)}</td>
                ${complexityCells}
                <td>
                    <div class="actions-cell">
                        <button type="button" class="btn btn-secondary btn-sm" data-action="edit" data-item="${encoded}">Sửa</button>
                        <button type="button" class="btn btn-danger btn-sm" data-action="delete" data-item="${encoded}">Xóa</button>
                    </div>
                </td>
            </tr>`;
    })
    .join("");

  body.innerHTML = `
        <div class="complexity-toolbar">
            <label>
                Loại hình xử lý
                <select id="complexityProcessFilter">
                    <option value="">Tất cả</option>
                    ${(state.options?.process_types || [])
                      .map(
                        (value) =>
                          `<option value="${escapeHtml(value)}">${escapeHtml(
                            value
                          )}</option>`
                      )
                      .join("")}
                </select>
            </label>
            <label>
                Tìm item
                <input id="complexityKeyword" placeholder="Nhập tên item..." />
            </label>
            <button type="button" class="btn btn-secondary" id="filterComplexityBtn">Lọc</button>
        </div>
        <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Process Type</th>
                        <th>Item</th>
                        <th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;

  $("filterComplexityBtn").addEventListener("click", filterRenderedRows);
}

function filterRenderedRows() {
  const processType = $("complexityProcessFilter").value;
  const keyword = $("complexityKeyword").value.trim().toLowerCase();
  const rows = $("complexityBody").querySelectorAll("tbody tr");

  rows.forEach((row) => {
    const rowProcessType = row.cells[0].textContent.trim();
    const itemName = row.cells[1].textContent.trim().toLowerCase();
    const visible =
      (!processType || rowProcessType === processType) &&
      (!keyword || itemName.includes(keyword));
    row.style.display = visible ? "" : "none";
  });
}

function openModal(item = null) {
  if (item && item.complexity_id == null) {
    showToast("API không trả complexity_id cho bản ghi cần sửa.", true);
    return;
  }

  state.editingId = item ? Number(item.complexity_id) : null;
  state.editingDisplayOrder = Number(item?.display_order ?? 0);
  $("complexityModalTitle").textContent = item
    ? "Sửa Complexity"
    : "Thêm Complexity";
  $("complexityProcessType").value =
    item?.process_type ?? state.options.process_types[0];
  $("complexityItemName").value = item?.item_name ?? "";

  for (let index = 1; index <= 5; index += 1) {
    $(`complexityC${index}`).value = item?.[`c${index}_description`] ?? "";
  }

  $("complexityFormError").textContent = "";
  $("complexityFormError").classList.add("hidden");
  $("complexityModal").classList.remove("hidden");
}

function closeModal() {
  $("complexityModal").classList.add("hidden");
  $("complexityForm").reset();
  $("complexityFormError").classList.add("hidden");
  state.editingId = null;
  state.editingDisplayOrder = 0;
}

function formPayload() {
  const payload = {
    process_type: $("complexityProcessType").value,
    item_name: $("complexityItemName").value.trim(),
    display_order: state.editingDisplayOrder,
  };

  for (let index = 1; index <= 5; index += 1) {
    payload[`c${index}_description`] =
      $(`complexityC${index}`).value.trim() || null;
  }
  return payload;
}

async function saveComplexity(event) {
  event.preventDefault();
  const isEdit = state.editingId !== null;
  const url = isEdit ? `${API}/${state.editingId}` : API;
  const method = isEdit ? "PUT" : "POST";

  $("saveComplexityBtn").disabled = true;
  try {
    await request(url, { method, body: JSON.stringify(formPayload()) });
    showToast(
      isEdit ? "Cập nhật complexity thành công" : "Thêm complexity thành công"
    );
    closeModal();
    await loadComplexities();
  } catch (error) {
    $("complexityFormError").textContent = error.message;
    $("complexityFormError").classList.remove("hidden");
  } finally {
    $("saveComplexityBtn").disabled = false;
  }
}

async function deleteComplexity(item) {
  if (!window.confirm(`Xóa item: ${item.item_name}?`)) return;
  try {
    await request(`${API}/${item.complexity_id}`, { method: "DELETE" });
    showToast("Xóa complexity thành công");
    await loadComplexities();
  } catch (error) {
    showToast(error.message, true);
  }
}

function showToast(message, isError = false) {
  const toast = $("complexityToast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function bindEvents() {
  $("addComplexityBtn").addEventListener("click", () => openModal());
  $("closeComplexityModal").addEventListener("click", closeModal);
  $("cancelComplexityBtn").addEventListener("click", closeModal);
  $("complexityForm").addEventListener("submit", saveComplexity);
  $("complexityModal").addEventListener("click", (event) => {
    if (event.target === $("complexityModal")) closeModal();
  });
  $("complexityBody").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const item = JSON.parse(decodeURIComponent(button.dataset.item));
    if (button.dataset.action === "edit") openModal(item);
    if (button.dataset.action === "delete") deleteComplexity(item);
  });
}

(async function initializeComplexityManager() {
  bindEvents();
  try {
    await loadOptions();
    await loadComplexities();
  } catch (error) {
    showToast(error.message, true);
  }
})();
