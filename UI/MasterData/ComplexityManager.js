// ──────────────────────────────────────────────
//  Complexity Manager - Quản lý độ phức tạp
// ──────────────────────────────────────────────

// ─── State ───
let complexityData = [
    { id: 1, name: 'Thấp', level: 1, color: '#4caf50', description: 'Thay đổi đơn giản, ít ảnh hưởng' },
    { id: 2, name: 'Trung bình', level: 2, color: '#ff9800', description: 'Thay đổi vừa, ảnh hưởng một số module' },
    { id: 3, name: 'Cao', level: 3, color: '#f44336', description: 'Thay đổi lớn, ảnh hưởng nhiều module' },
];

let nextComplexityId = 4;

// ─── DOM refs ───
const complexityBody = document.getElementById('complexityBody');
const complexityCount = document.getElementById('complexityCount');

// ─── Helpers ───
function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
        "'": '&#39;' }[c]));
}

// ─── Render ───
function renderComplexity() {
    complexityCount.textContent = complexityData.length;
    if (!complexityData.length) {
        complexityBody.innerHTML = `<div class="empty"><div class="glyph">— · · —</div>Chưa có dữ liệu độ phức tạp.</div>`;
        return;
    }

    let html = `<div class="table-scroll"><table class="data-table">
        <thead><tr>
            <th>ID</th>
            <th>Tên</th>
            <th>Level</th>
            <th>Màu</th>
            <th>Mô tả</th>
            <th>Thao tác</th>
        </tr></thead><tbody>`;

    complexityData.forEach(item => {
        const colorClass = item.level === 1 ? 'tag-blue' : item.level === 2 ? 'tag-amber' : 'tag-red';
        html += `<tr>
            <td>${item.id}</td>
            <td><strong>${esc(item.name)}</strong></td>
            <td><span class="tag ${colorClass}">Level ${item.level}</span></td>
            <td><span style="display:inline-block;width:20px;height:20px;background:${item.color};border-radius:2px;border:1px solid #ddd;"></span></td>
            <td>${esc(item.description)}</td>
            <td>
                <div class="actions-cell">
                    <button class="btn btn-secondary btn-sm" onclick="window.editComplexity(${item.id})">✏️</button>
                    <button class="btn btn-danger btn-sm" onclick="window.deleteComplexity(${item.id})">🗑️</button>
                </div>
            </td>
        </tr>`;
    });

    html += `</tbody></table></div>`;
    complexityBody.innerHTML = html;
}

// ─── CRUD Operations ───
function addComplexity() {
    const name = prompt('Nhập tên độ phức tạp:');
    if (!name) return;
    const level = parseInt(prompt('Nhập level (1, 2, 3, ...):') || '1');
    const color = prompt('Nhập màu (hex, VD: #4caf50):') || '#4caf50';
    const description = prompt('Nhập mô tả:') || '';

    complexityData.push({
        id: nextComplexityId++,
        name,
        level,
        color,
        description
    });
    renderComplexity();
}

function editComplexity(id) {
    const item = complexityData.find(c => c.id === id);
    if (!item) return;

    const name = prompt('Tên độ phức tạp:', item.name);
    if (name === null) return;
    const level = parseInt(prompt('Level:', item.level) || item.level);
    const color = prompt('Màu:', item.color) || item.color;
    const description = prompt('Mô tả:', item.description) || item.description;

    item.name = name || item.name;
    item.level = level;
    item.color = color;
    item.description = description;
    renderComplexity();
}

function deleteComplexity(id) {
    if (!confirm('Bạn có chắc chắn muốn xóa độ phức tạp này?')) return;
    complexityData = complexityData.filter(c => c.id !== id);
    renderComplexity();
}

// ─── Export to global scope ───
window.addComplexity = addComplexity;
window.editComplexity = editComplexity;
window.deleteComplexity = deleteComplexity;

// ─── Event Listeners ───
document.getElementById('addComplexityBtn').addEventListener('click', addComplexity);

// ─── Init ───
renderComplexity();

console.log('✅ Complexity Manager loaded');