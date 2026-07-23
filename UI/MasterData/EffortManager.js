// ──────────────────────────────────────────────
//  Effort Manager - Quản lý Effort (Nỗ lực)
// ──────────────────────────────────────────────

// ─── State ───
let effortData = [
    { id: 1, name: 'Nhỏ', hours: 4, days: 0.5, description: 'Công việc nhỏ, hoàn thành trong nửa ngày' },
    { id: 2, name: 'Vừa', hours: 16, days: 2, description: 'Công việc vừa, hoàn thành trong 2 ngày' },
    { id: 3, name: 'Lớn', hours: 40, days: 5, description: 'Công việc lớn, hoàn thành trong 1 tuần' },
    { id: 4, name: 'Rất lớn', hours: 80, days: 10, description: 'Công việc rất lớn, hoàn thành trong 2 tuần' },
];

let nextEffortId = 5;

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
            <th>ID</th>
            <th>Tên</th>
            <th>Giờ</th>
            <th>Ngày</th>
            <th>Mô tả</th>
            <th>Thao tác</th>
        </tr></thead><tbody>`;

    effortData.forEach(item => {
        const tagClass = item.hours <= 4 ? 'tag-blue' : item.hours <= 16 ? 'tag-amber' : 'tag-red';
        html += `<tr>
            <td>${item.id}</td>
            <td><strong>${esc(item.name)}</strong></td>
            <td><span class="tag ${tagClass}">${item.hours}h</span></td>
            <td>${item.days} ngày</td>
            <td>${esc(item.description)}</td>
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
    const name = prompt('Nhập tên effort:');
    if (!name) return;
    const hours = parseFloat(prompt('Nhập số giờ:') || '0');
    const days = parseFloat(prompt('Nhập số ngày:') || '0');
    const description = prompt('Nhập mô tả:') || '';

    effortData.push({
        id: nextEffortId++,
        name,
        hours,
        days,
        description
    });
    renderEffort();
}

function editEffort(id) {
    const item = effortData.find(e => e.id === id);
    if (!item) return;

    const name = prompt('Tên effort:', item.name);
    if (name === null) return;
    const hours = parseFloat(prompt('Số giờ:', item.hours) || item.hours);
    const days = parseFloat(prompt('Số ngày:', item.days) || item.days);
    const description = prompt('Mô tả:', item.description) || item.description;

    item.name = name || item.name;
    item.hours = hours;
    item.days = days;
    item.description = description;
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