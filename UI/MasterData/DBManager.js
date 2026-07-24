const API = "http://127.0.0.1:8000/api/v1/database-tables";

const state = {
  editingId: null,
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

async function loadDatabaseTables() {
  try {
    const data = await request(API);
    $("dbCount").textContent = data.total;
    renderTable(data.items);
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderTable(items) {
  const body = $("dbBody");

  if (!items.length) {
    body.innerHTML = `
            <div class="empty">
                <div class="glyph">— · · —</div>
                Chưa có dữ liệu database.
            </div>`;
    return;
  }

  const rows = items
    .map((item) => {
      const encoded = encodeURIComponent(JSON.stringify(item));
      return `
            <tr>
                <td>${escapeHtml(item.schema_name)}</td>
                <td><span class="tag tag-blue">${escapeHtml(
                  item.table_name
                )}</span></td>
                <td class="db-columns-cell">${escapeHtml(
                  item.columns_info
                )}</td>
                <td>${escapeHtml(item.table_description)}</td>
                <td>${escapeHtml(item.module_name)}</td>
                <td><span class="tag ${
                  item.active_yn === "N" ? "tag-red" : ""
                }">${escapeHtml(item.active_yn)}</span></td>
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
        <div class="db-toolbar">
            <label>
                Schema
                <input id="dbSchemaFilter" placeholder="effort_db" />
            </label>
            <label>
                Tìm kiếm
                <input id="dbKeywordFilter" placeholder="Table, mô tả, module..." />
            </label>
            <label>
                Active
                <select id="dbActiveFilter">
                    <option value="">Tất cả</option>
                    <option value="Y">Y</option>
                    <option value="N">N</option>
                </select>
            </label>
            <button type="button" class="btn btn-secondary" id="dbFilterBtn">Lọc</button>
            <button type="button" class="btn btn-secondary" id="dbResetBtn">Reset</button>
        </div>
        <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Schema</th>
                        <th>Table Name</th>
                        <th>Columns Info</th>
                        <th>Description</th>
                        <th>Module</th>
                        <th>Active</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;

  $("dbFilterBtn").addEventListener("click", applyFilter);
  $("dbResetBtn").addEventListener("click", () => {
    $("dbSchemaFilter").value = "";
    $("dbKeywordFilter").value = "";
    $("dbActiveFilter").value = "";
    applyFilter();
  });
}

function applyFilter() {
  const schema = $("dbSchemaFilter").value.trim().toLowerCase();
  const keyword = $("dbKeywordFilter").value.trim().toLowerCase();
  const active = $("dbActiveFilter").value;
  const rows = $("dbBody").querySelectorAll("tbody tr");

  rows.forEach((row) => {
    const rowSchema = row.cells[0].textContent.trim().toLowerCase();
    const searchable = [row.cells[1], row.cells[2], row.cells[3], row.cells[4]]
      .map((cell) => cell.textContent.trim().toLowerCase())
      .join(" ");
    const rowActive = row.cells[5].textContent.trim();
    const visible =
      (!schema || rowSchema.includes(schema)) &&
      (!keyword || searchable.includes(keyword)) &&
      (!active || rowActive === active);
    row.style.display = visible ? "" : "none";
  });
}

function openModal(item = null) {
  state.editingId = item ? Number(item.database_id) : null;
  $("dbModalTitle").textContent = item
    ? "Sửa Database Table"
    : "Thêm Database Table";
  $("dbSchemaName").value = item?.schema_name ?? "effort_db";
  $("dbTableName").value = item?.table_name ?? "";
  $("dbColumnsInfo").value = item?.columns_info ?? "";
  $("dbTableDescription").value = item?.table_description ?? "";
  $("dbModuleName").value = item?.module_name ?? "";
  $("dbActiveYn").value = item?.active_yn ?? "Y";
  $("dbFormError").textContent = "";
  $("dbFormError").classList.add("hidden");
  $("dbModal").classList.remove("hidden");
}

function closeModal() {
  $("dbModal").classList.add("hidden");
  $("dbForm").reset();
  $("dbFormError").classList.add("hidden");
  state.editingId = null;
}

function formPayload() {
  return {
    schema_name: $("dbSchemaName").value.trim(),
    table_name: $("dbTableName").value.trim(),
    columns_info: $("dbColumnsInfo").value.trim() || null,
    table_description: $("dbTableDescription").value.trim() || null,
    module_name: $("dbModuleName").value.trim() || null,
    active_yn: $("dbActiveYn").value,
  };
}

async function saveDatabaseTable(event) {
  event.preventDefault();
  const isEdit = state.editingId !== null;
  const url = isEdit ? `${API}/${state.editingId}` : API;
  const method = isEdit ? "PUT" : "POST";

  $("saveDbBtn").disabled = true;
  try {
    await request(url, { method, body: JSON.stringify(formPayload()) });
    showToast(
      isEdit
        ? "Cập nhật database table thành công"
        : "Thêm database table thành công"
    );
    closeModal();
    await loadDatabaseTables();
  } catch (error) {
    $("dbFormError").textContent = error.message;
    $("dbFormError").classList.remove("hidden");
  } finally {
    $("saveDbBtn").disabled = false;
  }
}

async function deleteDatabaseTable(item) {
  if (
    !window.confirm(`Xóa table master: ${item.schema_name}.${item.table_name}?`)
  )
    return;
  try {
    await request(`${API}/${item.database_id}`, { method: "DELETE" });
    showToast("Xóa database table thành công");
    await loadDatabaseTables();
  } catch (error) {
    showToast(error.message, true);
  }
}

function showToast(message, isError = false) {
  const toast = $("dbToast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function bindEvents() {
  $("addDbBtn").addEventListener("click", () => openModal());
  $("closeDbModal").addEventListener("click", closeModal);
  $("cancelDbBtn").addEventListener("click", closeModal);
  $("dbForm").addEventListener("submit", saveDatabaseTable);
  $("dbModal").addEventListener("click", (event) => {
    if (event.target === $("dbModal")) closeModal();
  });
  $("dbBody").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const item = JSON.parse(decodeURIComponent(button.dataset.item));
    if (button.dataset.action === "edit") openModal(item);
    if (button.dataset.action === "delete") deleteDatabaseTable(item);
  });
}

bindEvents();
loadDatabaseTables();
