const API = "http://127.0.0.1:8000/api/v1/effort-details";

const state = {
  items: [],
  options: null,
  editingKey: null,
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

  fillOptions($("effortDevType"), state.options.dev_type);
  fillOptions($("effortDevSubType"), state.options.dev_sub_type);
  fillOptions($("effortChangeType"), state.options.change_type);
  fillOptions($("effortComplexity"), state.options.complexity);
}

async function loadEfforts() {
  try {
    const data = await request(`${API}?page=1&size=100`);
    state.items = data.items;
    $("effortCount").textContent = data.total;
    renderEffortTable(data.items);
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderEffortTable(items) {
  const body = $("effortBody");

  if (!items.length) {
    body.innerHTML = `
            <div class="empty">
                <div class="glyph">— · · —</div>
                Chưa có dữ liệu effort.
            </div>`;
    return;
  }

  const rows = items
    .map((item) => {
      const encoded = encodeURIComponent(JSON.stringify(item));
      return `
            <tr>
                <td>${escapeHtml(item.dev_type)}</td>
                <td>${escapeHtml(item.dev_sub_type)}</td>
                <td><span class="tag ${
                  item.change_type === "CHANGE" ? "tag-amber" : ""
                }">${escapeHtml(item.change_type)}</span></td>
                <td><span class="tag tag-blue">${escapeHtml(
                  item.complexity
                )}</span></td>
                <td>${Number(item.standard_effort).toFixed(2)}</td>
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
        <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Dev Type</th>
                        <th>Dev Sub Type</th>
                        <th>Change Type</th>
                        <th>Complexity</th>
                        <th>Standard Effort</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

function keyOf(item) {
  return {
    dev_type: item.dev_type,
    dev_sub_type: item.dev_sub_type,
    change_type: item.change_type,
    complexity: item.complexity,
  };
}

function keyQuery(key) {
  return new URLSearchParams(key).toString();
}

function openEffortModal(item = null) {
  state.editingKey = item ? keyOf(item) : null;
  $("effortModalTitle").textContent = item
    ? "Sửa Effort Detail"
    : "Thêm Effort Detail";

  $("effortDevType").value = item?.dev_type ?? state.options.dev_type[0];
  $("effortDevSubType").value =
    item?.dev_sub_type ?? state.options.dev_sub_type[0];
  $("effortChangeType").value =
    item?.change_type ?? state.options.change_type[0];
  $("effortComplexity").value = item?.complexity ?? state.options.complexity[0];
  $("effortStandardEffort").value = item?.standard_effort ?? "";
  $("effortFormError").textContent = "";
  $("effortFormError").classList.add("hidden");
  $("effortModal").classList.remove("hidden");
}

function closeEffortModal() {
  $("effortModal").classList.add("hidden");
  $("effortForm").reset();
  $("effortFormError").classList.add("hidden");
  state.editingKey = null;
}

function formPayload() {
  return {
    dev_type: $("effortDevType").value,
    dev_sub_type: $("effortDevSubType").value,
    change_type: $("effortChangeType").value,
    complexity: $("effortComplexity").value,
    standard_effort: $("effortStandardEffort").value,
  };
}

async function saveEffort(event) {
  event.preventDefault();
  const isEdit = state.editingKey !== null;
  const url = isEdit ? `${API}/detail?${keyQuery(state.editingKey)}` : API;
  const method = isEdit ? "PUT" : "POST";

  $("saveEffortBtn").disabled = true;
  try {
    await request(url, {
      method,
      body: JSON.stringify(formPayload()),
    });
    showToast(isEdit ? "Cập nhật effort thành công" : "Thêm effort thành công");
    closeEffortModal();
    await loadEfforts();
  } catch (error) {
    $("effortFormError").textContent = error.message;
    $("effortFormError").classList.remove("hidden");
  } finally {
    $("saveEffortBtn").disabled = false;
  }
}

async function deleteEffort(item) {
  if (
    !window.confirm(
      `Xóa ${item.dev_type} / ${item.dev_sub_type} / ${item.change_type} / ${item.complexity}?`
    )
  ) {
    return;
  }

  try {
    await request(`${API}/detail?${keyQuery(keyOf(item))}`, {
      method: "DELETE",
    });
    showToast("Xóa effort thành công");
    await loadEfforts();
  } catch (error) {
    showToast(error.message, true);
  }
}

function showToast(message, isError = false) {
  const toast = $("masterToast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function bindEvents() {
  $("addEffortBtn").addEventListener("click", () => openEffortModal());
  $("closeEffortModal").addEventListener("click", closeEffortModal);
  $("cancelEffortBtn").addEventListener("click", closeEffortModal);
  $("effortForm").addEventListener("submit", saveEffort);
  $("effortModal").addEventListener("click", (event) => {
    if (event.target === $("effortModal")) closeEffortModal();
  });
  $("effortBody").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const item = JSON.parse(decodeURIComponent(button.dataset.item));
    if (button.dataset.action === "edit") openEffortModal(item);
    if (button.dataset.action === "delete") deleteEffort(item);
  });
}

(async function initializeEffortManager() {
  bindEvents();
  try {
    await loadOptions();
    await loadEfforts();
  } catch (error) {
    showToast(error.message, true);
  }
})();
