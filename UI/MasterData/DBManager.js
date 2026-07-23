// ──────────────────────────────────────────────
//  DB Manager - Quản lý Database
// ──────────────────────────────────────────────

// ─── State ───
let dbData = [
    { id: 1, name: 'MySQL Production', type: 'MySQL', host: 'localhost', port: 3306, database: 'task_management' },
    { id: 2, name: 'PostgreSQL Dev', type: 'PostgreSQL', host: 'dev-db.local', port: 5432, database: 'dev_db' },
    { id: 3, name: 'MongoDB Analytics', type: 'MongoDB', host: 'analytics.mongo', port: 27017, database: 'analytics' },
];

let nextDbId = 4;

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
            <th>ID</th>
            <th>Tên</th>
            <th>Loại</th>
            <th>Host</th>
            <th>Port</th>
            <th>Database</th>
            <th>Thao tác</th>
        </tr></thead><tbody>`;

    dbData.forEach(item => {
        html += `<tr>
            <td>${item.id}</td>
            <td><strong>${esc(item.name)}</strong></td>
            <td><span class="tag tag-blue">${esc(item.type)}</span></td>
            <td class="mono" style="font-family:var(--mono);font-size:11.5px;">${esc(item.host)}</td>
            <td>${item.port}</td>
            <td class="mono" style="font-family:var(--mono);font-size:11.5px;">${esc(item.database)}</td>
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
    const name = prompt('Nhập tên database:');
    if (!name) return;
    const type = prompt('Nhập loại database (MySQL, PostgreSQL, MongoDB, ...):') || 'MySQL';
    const host = prompt('Nhập host:') || 'localhost';
    const port = parseInt(prompt('Nhập port:') || '3306');
    const database = prompt('Nhập tên database:') || 'db';

    dbData.push({
        id: nextDbId++,
        name,
        type,
        host,
        port,
        database
    });
    renderDB();
}

function editDB(id) {
    const item = dbData.find(d => d.id === id);
    if (!item) return;

    const name = prompt('Tên database:', item.name);
    if (name === null) return;
    const type = prompt('Loại database:', item.type) || item.type;
    const host = prompt('Host:', item.host) || item.host;
    const port = parseInt(prompt('Port:', item.port) || item.port);
    const database = prompt('Database:', item.database) || item.database;

    item.name = name || item.name;
    item.type = type;
    item.host = host;
    item.port = port;
    item.database = database;
    renderDB();
}

function deleteDB(id) {
    if (!confirm('Bạn có chắc chắn muốn xóa database này?')) return;
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