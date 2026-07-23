// ──────────────────────────────────────────────
//  Complexity Manager - Quản lý độ phức tạp (C1-C5)
// ──────────────────────────────────────────────

// ─── State ───
let complexityData = [
    { 
        id: 1, 
        level: 'C1', 
        name: 'Rất thấp',
        criteria: 'Số lượng column ≤ 10, Business logic ≤ 5, UI đơn giản',
        description: 'Thay đổi đơn giản, ít ảnh hưởng, dễ thực hiện'
    },
    { 
        id: 2, 
        level: 'C2', 
        name: 'Thấp',
        criteria: 'Số lượng column 10-15, Business logic 6-10, UI trung bình',
        description: 'Thay đổi tương đối đơn giản, ảnh hưởng ít module'
    },
    { 
        id: 3, 
        level: 'C3', 
        name: 'Trung bình',
        criteria: 'Số lượng column 15-20, Business logic 11-15, UI phức tạp',
        description: 'Thay đổi vừa, ảnh hưởng một số module'
    },
    { 
        id: 4, 
        level: 'C4', 
        name: 'Cao',
        criteria: 'Số lượng column 20-25, Business logic > 15, UI rất phức tạp',
        description: 'Thay đổi lớn, ảnh hưởng nhiều module'
    },
    { 
        id: 5, 
        level: 'C5', 
        name: 'Rất cao',
        criteria: 'Số lượng column > 25, Business logic > 20, UI đặc biệt phức tạp',
        description: 'Thay đổi rất lớn, ảnh hưởng toàn hệ thống, cần thảo luận kỹ'
    },
];

let nextComplexityId = 6;

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
            <th style="width:60px;">Level</th>
            <th style="min-width:120px;">Tên</th>
            <th style="min-width:250px;">Tiêu chí đánh giá</th>
            <th style="min-width:200px;">Mô tả</th>
            <th style="width:120px;">Thao tác</th>
        </tr></thead><tbody>`;

    complexityData.forEach(item => {
        const colorClass = item.level === 'C1' ? 'tag-blue' : 
                          item.level === 'C2' ? 'tag-blue' :
                          item.level === 'C3' ? 'tag-amber' : 
                          item.level === 'C4' ? 'tag-red' : 'tag-red';
        html += `<tr>
            <td style="text-align:center;"><span class="tag ${colorClass}" style="font-size:14px;font-weight:700;">${esc(item.level)}</span></td>
            <td><strong>${esc(item.name)}</strong></td>
            <td style="font-size:11.5px;">${esc(item.criteria)}</td>
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
    const level = prompt('Nhập level (C1, C2, C3, C4, C5):');
    if (!level) return;
    const name = prompt('Nhập tên độ phức tạp:') || '';
    const criteria = prompt('Nhập tiêu chí đánh giá:') || '';
    const description = prompt('Nhập mô tả:') || '';

    complexityData.push({
        id: nextComplexityId++,
        level,
        name,
        criteria,
        description
    });
    renderComplexity();
}

function editComplexity(id) {
    const item = complexityData.find(c => c.id === id);
    if (!item) return;

    const level = prompt('Level:', item.level);
    if (level === null) return;
    const name = prompt('Tên:', item.name) || item.name;
    const criteria = prompt('Tiêu chí:', item.criteria) || item.criteria;
    const description = prompt('Mô tả:', item.description) || item.description;

    item.level = level || item.level;
    item.name = name;
    item.criteria = criteria;
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