// ──────────────────────────────────────────────
//  Complexity Manager - Quản lý độ phức tạp (C1-C5)
//  Theo bảng tiêu chí chi tiết
// ──────────────────────────────────────────────

// ─── State ───
let complexityData = [
    { 
        id: 1, 
        level: 'C1',
        online_table: '2개이하 (Dưới 2)',
        column_count: '10개 이하 (Dưới 10)',
        validation_logic: '5개 이하 (Dưới 5)',
        business_logic: '없음 (Không có)',
        ui_component: 'Đơn giản',
        description: 'Độ phức tạp thấp nhất, ít xử lý logic'
    },
    { 
        id: 2, 
        level: 'C2',
        online_table: '3개이하 (Dưới 3)',
        column_count: '10~20',
        validation_logic: '6~10',
        business_logic: '1~5',
        ui_component: 'Trung bình',
        description: 'Độ phức tạp thấp, logic vừa phải'
    },
    { 
        id: 3, 
        level: 'C3',
        online_table: '4개이하 (Dưới 4)',
        column_count: '15~25',
        validation_logic: '11~15',
        business_logic: '6~10',
        ui_component: 'Phức tạp',
        description: 'Độ phức tạp trung bình, nhiều logic xử lý'
    },
    { 
        id: 4, 
        level: 'C4',
        online_table: '5개 이상 (Trên 5)',
        column_count: '25 이상 (Trên 25)',
        validation_logic: '15개 초과 (Vượt quá 15)',
        business_logic: '10 초과 (Vượt quá 10)',
        ui_component: 'Rất phức tạp',
        description: 'Độ phức tạp cao, cần thảo luận kỹ'
    },
    { 
        id: 5, 
        level: 'C5',
        online_table: '특이사항 (Đặc thù)',
        column_count: 'Đặc biệt',
        validation_logic: 'Đặc biệt',
        business_logic: 'Đặc biệt',
        ui_component: 'Đặc biệt phức tạp',
        description: 'Độ phức tạp đặc biệt, cần thảo luận chi tiết'
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

    let html = `
    <div style="overflow-x:auto;margin-bottom:16px;">
        <div style="background:var(--green-head);border:1px solid var(--green-head-strong);padding:10px 14px;margin-bottom:12px;border-radius:2px;">
            <div style="display:grid;grid-template-columns:80px 1fr 1fr 1fr 1fr 1fr 120px;gap:6px;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#2d4227;">
                <div>Level</div>
                <div>Online Table<br><span style="font-weight:400;font-size:10px;">(Loại trừ bảng code)</span></div>
                <div>Số lượng column/item<br><span style="font-weight:400;font-size:10px;">(Screen, handling)</span></div>
                <div>Xử lý phức tạp<br><span style="font-weight:400;font-size:10px;">(Validation số 1)</span></div>
                <div>Xử lý phức tạp<br><span style="font-weight:400;font-size:10px;">(Business logic, Tính toán, UI)</span></div>
                <div>UI Elements<br><span style="font-weight:400;font-size:10px;">(UI component)</span></div>
                <div>Thao tác</div>
            </div>
        </div>
        
        <div style="display:flex;flex-direction:column;gap:4px;">`;

    complexityData.forEach((item, index) => {
        const colorClass = item.level === 'C1' ? 'tag-blue' : 
                          item.level === 'C2' ? 'tag-blue' :
                          item.level === 'C3' ? 'tag-amber' : 
                          item.level === 'C4' ? 'tag-red' : 'tag-red';
        
        const bgColor = index % 2 === 0 ? '#fbfcfa' : '#ffffff';
        
        html += `
            <div style="display:grid;grid-template-columns:80px 1fr 1fr 1fr 1fr 1fr 120px;gap:6px;padding:10px 12px;background:${bgColor};border:1px solid var(--line);border-radius:2px;align-items:center;">
                <div style="text-align:center;">
                    <span class="tag ${colorClass}" style="font-size:14px;font-weight:700;padding:4px 10px;">${esc(item.level)}</span>
                </div>
                <div style="font-size:12.5px;">${esc(item.online_table)}</div>
                <div style="font-size:12.5px;">${esc(item.column_count)}</div>
                <div style="font-size:12.5px;">${esc(item.validation_logic)}</div>
                <div style="font-size:12.5px;">${esc(item.business_logic)}</div>
                <div style="font-size:12.5px;">${esc(item.ui_component)}</div>
                <div>
                    <div class="actions-cell" style="justify-content:center;">
                        <button class="btn btn-secondary btn-sm" onclick="window.editComplexity(${item.id})">✏️</button>
                        <button class="btn btn-danger btn-sm" onclick="window.deleteComplexity(${item.id})">🗑️</button>
                    </div>
                </div>
            </div>
        `;
    });

    html += `
        </div>
    </div>
    
    <!-- Legend -->
    <div style="background:var(--accent-soft);border:1px solid var(--line);padding:10px 14px;border-radius:2px;font-size:11px;color:var(--ink-soft);">
        <div style="display:flex;gap:20px;flex-wrap:wrap;">
            <div><span class="tag tag-blue">C1-C2</span> Độ phức tạp thấp</div>
            <div><span class="tag tag-amber">C3</span> Độ phức tạp trung bình</div>
            <div><span class="tag tag-red">C4-C5</span> Độ phức tạp cao, cần thảo luận</div>
           
        </div>
    </div>`;

    complexityBody.innerHTML = html;
}

// ─── CRUD Operations ───
function addComplexity() {
    const level = prompt('Nhập level (C1, C2, C3, C4, C5):');
    if (!level) return;
    
    const online_table = prompt('Online Table (VD: 2개이하, 3개이하, 4개이하, 5개 이상, 특이사항):') || '';
    const column_count = prompt('Số lượng column (VD: 10개 이하, 10~20, 15~25, 25 이상, Đặc biệt):') || '';
    const validation_logic = prompt('Validation logic (VD: 5개 이하, 6~10, 11~15, 15개 초과, Đặc biệt):') || '';
    const business_logic = prompt('Business logic (VD: 없음, 1~5, 6~10, 10 초과, Đặc biệt):') || '';
    const ui_component = prompt('UI Component (VD: Đơn giản, Trung bình, Phức tạp, Rất phức tạp, Đặc biệt):') || '';
    const description = prompt('Mô tả:') || '';

    complexityData.push({
        id: nextComplexityId++,
        level,
        online_table,
        column_count,
        validation_logic,
        business_logic,
        ui_component,
        description
    });
    renderComplexity();
}

function editComplexity(id) {
    const item = complexityData.find(c => c.id === id);
    if (!item) return;

    const level = prompt('Level:', item.level);
    if (level === null) return;
    
    const online_table = prompt('Online Table:', item.online_table) || item.online_table;
    const column_count = prompt('Số lượng column:', item.column_count) || item.column_count;
    const validation_logic = prompt('Validation logic:', item.validation_logic) || item.validation_logic;
    const business_logic = prompt('Business logic:', item.business_logic) || item.business_logic;
    const ui_component = prompt('UI Component:', item.ui_component) || item.ui_component;
    const description = prompt('Mô tả:', item.description) || item.description;

    item.level = level || item.level;
    item.online_table = online_table;
    item.column_count = column_count;
    item.validation_logic = validation_logic;
    item.business_logic = business_logic;
    item.ui_component = ui_component;
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