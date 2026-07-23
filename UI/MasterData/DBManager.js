// ──────────────────────────────────────────────
//  DB Manager - Quản lý Database
// ──────────────────────────────────────────────

// ─── State ───
let dbData = [
    { 
        id: 1, 
        table_name: 'TB_USER', 
        schema: 'PUBLIC', 
        columns: 'USER_ID, USER_NAME, EMAIL, STATUS, CREATED_AT', 
        description: 'Bảng quản lý thông tin người dùng' 
    },
    { 
        id: 2, 
        table_name: 'TB_ORDER', 
        schema: 'PUBLIC', 
        columns: 'ORDER_ID, USER_ID, ORDER_DATE, TOTAL_AMOUNT, STATUS', 
        description: 'Bảng quản lý đơn hàng' 
    },
    { 
        id: 3, 
        table_name: 'TB_PRODUCT', 
        schema: 'PUBLIC', 
        columns: 'PRODUCT_ID, PRODUCT_NAME, CATEGORY, PRICE, STOCK_QUANTITY', 
        description: 'Bảng quản lý sản phẩm' 
    },
    { 
        id: 4, 
        table_name: 'TB_CMCC_ENTR_ATTR_M', 
        schema: 'CMCC', 
        columns: 'ENTR_ID, ATTR_ID, ATTR_VALUE, STATUS, REG_DT', 
        description: 'Bảng quản lý thuộc tính đầu vào CMCC' 
    },
];

let nextDbId = 5;

// ─── DOM refs ───
const dbBody = document.getElementById('dbBody');
const dbCount = document.getElementById('dbCount');

// ─── Helpers ───
function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
        "'": '&#39;' }[c]));
}

// ─── Render ───
function renderDB() {
    dbCount.textContent = dbData.length;
    if (!dbData.length) {
        dbBody.innerHTML = `<div class="empty"><div class="glyph">— · · —</div>Chưa có dữ liệu database.</div>`;
        return;
    }

    let html = `<div class="table-scroll"><table class="data-table">
        <thead><tr>
            <th style="width:50px;">ID</th>
            <th style="min-width:150px;">Tên bảng</th>
            <th style="min-width:120px;">Schema</th>
            <th style="min-width:250px;">Các cột</th>
            <th style="min-width:200px;">Mô tả</th>
            <th style="width:120px;">Thao tác</th>
        </tr></thead><tbody>`;

    dbData.forEach(item => {
        html += `<tr>
            <td style="text-align:center;">${item.id}</td>
            <td><strong style="font-family:var(--mono);font-size:12px;">${esc(item.table_name)}</strong></td>
            <td><span class="tag tag-blue">${esc(item.schema)}</span></td>
            <td style="font-family:var(--mono);font-size:11px;">${esc(item.columns)}</td>
            <td>${esc(item.description)}</td>
            <td>
                <div class="actions-cell">
                    <button class="btn btn-secondary btn-sm" onclick="window.editDB(${item.id})">✏️</button>
                    <button class="btn btn-danger btn-sm" onclick="window.deleteDB(${item.id})">🗑️</button>
                </div>
            </td>
        </tr>`;
    });

    html += `</tbody></table></div>`;
    dbBody.innerHTML = html;
}

// ─── CRUD Operations ───
function addDB() {
    const table_name = prompt('Nhập tên bảng:');
    if (!table_name) return;
    const schema = prompt('Nhập schema:') || 'PUBLIC';
    const columns = prompt('Nhập danh sách cột (cách nhau bởi dấu phẩy):') || '';
    const description = prompt('Nhập mô tả bảng:') || '';

    dbData.push({
        id: nextDbId++,
        table_name,
        schema,
        columns,
        description
    });
    renderDB();
}

function editDB(id) {
    const item = dbData.find(d => d.id === id);
    if (!item) return;

    const table_name = prompt('Tên bảng:', item.table_name);
    if (table_name === null) return;
    const schema = prompt('Schema:', item.schema) || item.schema;
    const columns = prompt('Các cột:', item.columns) || item.columns;
    const description = prompt('Mô tả:', item.description) || item.description;

    item.table_name = table_name || item.table_name;
    item.schema = schema;
    item.columns = columns;
    item.description = description;
    renderDB();
}

function deleteDB(id) {
    if (!confirm('Bạn có chắc chắn muốn xóa bảng này?')) return;
    dbData = dbData.filter(d => d.id !== id);
    renderDB();
}

// ─── Export to global scope ───
window.addDB = addDB;
window.editDB = editDB;
window.deleteDB = deleteDB;

// ─── Event Listeners ───
document.getElementById('addDbBtn').addEventListener('click', addDB);

// ─── Init ───
renderDB();

console.log('✅ DB Manager loaded');