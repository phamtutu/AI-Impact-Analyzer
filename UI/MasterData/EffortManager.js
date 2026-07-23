// ──────────────────────────────────────────────
//  Effort Manager - Quản lý Effort (Development Effort)
//  Theo bảng: Development Type, Change Type, Complexity
// ──────────────────────────────────────────────

// ─── State ───
let effortData = [
    // Web - Online_Web - New
    { id: 1, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '신규 (New)', complexity: 'C0', effort: 1.1 },
    { id: 2, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '신규 (New)', complexity: 'C1', effort: 1.8 },
    { id: 3, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '신규 (New)', complexity: 'C2', effort: 3.2 },
    { id: 4, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '신규 (New)', complexity: 'C3', effort: 5.0 },
    { id: 5, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '신규 (New)', complexity: 'C4', effort: 7.4 },
    { id: 6, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '신규 (New)', complexity: 'C5', effort: 11.9 },
    // Web - Online_Web - Change
    { id: 7, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '변경 (Change)', complexity: 'C0', effort: 0.6 },
    { id: 8, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '변경 (Change)', complexity: 'C1', effort: 1.0 },
    { id: 9, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '변경 (Change)', complexity: 'C2', effort: 2.3 },
    { id: 10, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '변경 (Change)', complexity: 'C3', effort: 3.6 },
    { id: 11, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '변경 (Change)', complexity: 'C4', effort: 5.3 },
    { id: 12, dev_type: 'WEB', dev_sub_type: 'Online_Web', change_type: '변경 (Change)', complexity: 'C5', effort: 8.9 },
];

let nextEffortId = 13;

// ─── DOM refs ───
const effortBody = document.getElementById('effortBody');
const effortCount = document.getElementById('effortCount');

// ─── Helpers ───
function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
        "'": '&#39;' }[c]));
}

// ─── Render ───
function renderEffort() {
    effortCount.textContent = effortData.length;
    if (!effortData.length) {
        effortBody.innerHTML = `<div class="empty"><div class="glyph">— · · —</div>Chưa có dữ liệu effort.</div>`;
        return;
    }

    let html = `<div class="table-scroll"><table class="data-table">
        <thead><tr>
            <th style="width:50px;">ID</th>
            <th style="min-width:80px;">Dev Type</th>
            <th style="min-width:120px;">Dev Sub Type</th>
            <th style="min-width:130px;">Change Type</th>
            <th style="width:70px;">Complexity</th>
            <th style="width:100px;">Effort (ngày)</th>
            <th style="width:120px;">Thao tác</th>
        </tr></thead><tbody>`;

    effortData.forEach(item => {
        const colorClass = item.complexity === 'C0' || item.complexity === 'C1' ? 'tag-blue' :
                          item.complexity === 'C2' || item.complexity === 'C3' ? 'tag-amber' : 'tag-red';
        const changeClass = item.change_type.includes('신규') ? 'tag-blue' : 'tag-amber';
        html += `<tr>
            <td style="text-align:center;">${item.id}</td>
            <td><span class="tag">${esc(item.dev_type)}</span></td>
            <td>${esc(item.dev_sub_type)}</td>
            <td><span class="tag ${changeClass}">${esc(item.change_type)}</span></td>
            <td style="text-align:center;"><span class="tag ${colorClass}">${esc(item.complexity)}</span></td>
            <td style="text-align:center;font-weight:700;font-family:var(--mono);font-size:14px;color:var(--accent);">${item.effort}</td>
            <td>
                <div class="actions-cell">
                    <button class="btn btn-secondary btn-sm" onclick="window.editEffort(${item.id})">✏️</button>
                    <button class="btn btn-danger btn-sm" onclick="window.deleteEffort(${item.id})">🗑️</button>
                </div>
            </td>
        </tr>`;
    });

    html += `</tbody></table></div>`;
    effortBody.innerHTML = html;
}

// ─── CRUD Operations ───
function addEffort() {
    const dev_type = prompt('Nhập Development Type (WEB, APP, ...):') || 'WEB';
    const dev_sub_type = prompt('Nhập Development Sub Type (Online_Web, Mobile, ...):') || 'Online_Web';
    const change_type = prompt('Nhập Change Type (신규 (New), 변경 (Change)):') || '신규 (New)';
    const complexity = prompt('Nhập Complexity (C0, C1, C2, C3, C4, C5):') || 'C0';
    const effort = parseFloat(prompt('Nhập Effort (số ngày công):') || '0');

    effortData.push({
        id: nextEffortId++,
        dev_type,
        dev_sub_type,
        change_type,
        complexity,
        effort
    });
    renderEffort();
}

function editEffort(id) {
    const item = effortData.find(e => e.id === id);
    if (!item) return;

    const dev_type = prompt('Development Type:', item.dev_type) || item.dev_type;
    const dev_sub_type = prompt('Development Sub Type:', item.dev_sub_type) || item.dev_sub_type;
    const change_type = prompt('Change Type:', item.change_type) || item.change_type;
    const complexity = prompt('Complexity:', item.complexity) || item.complexity;
    const effort = parseFloat(prompt('Effort:', item.effort) || item.effort);

    item.dev_type = dev_type;
    item.dev_sub_type = dev_sub_type;
    item.change_type = change_type;
    item.complexity = complexity;
    item.effort = effort;
    renderEffort();
}

function deleteEffort(id) {
    if (!confirm('Bạn có chắc chắn muốn xóa effort này?')) return;
    effortData = effortData.filter(e => e.id !== id);
    renderEffort();
}

// ─── Export to global scope ───
window.addEffort = addEffort;
window.editEffort = editEffort;
window.deleteEffort = deleteEffort;

// ─── Event Listeners ───
document.getElementById('addEffortBtn').addEventListener('click', addEffort);

// ─── Init ───
renderEffort();

console.log('✅ Effort Manager loaded');