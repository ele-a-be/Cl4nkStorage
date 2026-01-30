
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cl4nk Storage</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --glass: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.1);
            --accent: #3b82f6;
            --danger: #ef4444;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
        body { background: var(--bg); color: var(--text); min-height: 100vh; overflow-x: hidden; }
        
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        /* Header */
        header { 
            display: flex; justify-content: space-between; align-items: center; 
            padding: 20px 0; margin-bottom: 30px;
            border-bottom: 1px solid var(--glass-border);
        }
        h1 { font-weight: 600; font-size: 1.5rem; display: flex; align-items: center; gap: 10px; }
        
        .btn {
            background: var(--accent); color: white; border: none; padding: 8px 16px; 
            border-radius: 8px; cursor: pointer; font-size: 0.9rem; transition: opacity 0.2s;
            display: inline-flex; align-items: center; gap: 5px; text-decoration: none;
        }
        .btn:hover { opacity: 0.9; }
        .btn-secondary { background: rgba(255,255,255,0.1); border: 1px solid var(--glass-border); }
        .btn-sm { padding: 4px 8px; font-size: 0.8rem; background: transparent; border: 1px solid var(--glass-border); }
        .btn-danger { color: var(--danger); border-color: var(--danger); }
        
        /* Grid */
        .file-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px;
        }
        .card {
            background: var(--glass); backdrop-filter: blur(10px);
            border: 1px solid var(--glass-border); border-radius: 16px;
            padding: 20px; position: relative;
            transition: transform 0.2s, background 0.2s;
        }
        .file-item {
            display: flex; flex-direction: column; align-items: center; text-align: center; cursor: pointer;
        }
        .file-item:hover { transform: translateY(-3px); background: rgba(255,255,255,0.05); }
        
        .icon { font-size: 3rem; margin-bottom: 10px; }
        .name { font-size: 0.9rem; word-break: break-all; line-height: 1.2; width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .meta { font-size: 0.7rem; color: var(--text-muted); margin-top: 5px; }

        /* Menus */
        .actions-btn {
            position: absolute; top: 10px; right: 10px; width: 24px; height: 24px;
            border-radius: 50%; display: flex; align-items: center; justify-content: center;
            cursor: pointer; opacity: 0; transition: opacity 0.2s; z-index: 10;
        }
        .file-item:hover .actions-btn, .actions-btn.active { opacity: 1; background: rgba(0,0,0,0.3); }

        .dropdown {
            position: absolute; top: 35px; right: 10px; width: 140px;
            background: #1e293b; border: 1px solid var(--glass-border); border-radius: 8px;
            overflow: hidden; z-index: 20; display: none; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        #sort-dropdown { top: 45px; right: 0; width: 160px; }
        
        .dropdown.show { display: block; }
        .dropdown-item {
            padding: 10px; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 8px;
            color: var(--text);
        }
        .dropdown-item:hover { background: rgba(255,255,255,0.05); }
        .dropdown-item.active { background: rgba(59, 130, 246, 0.2); color: var(--accent); }
        .dropdown-item.danger { color: var(--danger); }
        .dropdown-divider { height: 1px; background: var(--glass-border); margin: 4px 0; }

        /* Breadcrumbs */
        .breadcrumbs { display: flex; gap: 10px; margin-bottom: 20px; color: var(--accent); cursor: pointer; flex-wrap: wrap; }
        .breadcrumb-item:hover { text-decoration: underline; }

        /* Drag Drop Overlay */
        #drop-zone {
            position: fixed; top:0; left:0; width:100%; height:100%;
            background: rgba(15, 23, 42, 0.9); z-index: 200;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
            border: 4px dashed var(--accent); opacity: 0; pointer-events: none; transition: opacity 0.2s;
        }
        #drop-zone.active { opacity: 1; pointer-events: al; }
        
        /* Modal for Large Files */
        .modal-overlay {
            position: fixed; top:0; left:0; width:100%; height:100%;
            background: rgba(0,0,0,0.8); z-index: 300; display: none;
            justify-content: center; align-items: center;
        }
        .modal { background: #1e293b; padding: 30px; border-radius: 16px; max-width: 400px; text-align: center; }

        /* Feedback */
        #toast {
            position: fixed; bottom: 20px; right: 20px; background: #10b981; color: white; 
            padding: 10px 20px; border-radius: 8px; transform: translateY(100px); transition: transform 0.3s;
        }
        #toast.show { transform: translateY(0); }
        .toast-error { background: var(--danger) !important; }
        
        /* Login Screen */
        #login-screen { 
            position: fixed; top:0; left:0; width:100%; height:100%; 
            background: var(--bg); display: flex; justify-content: center; align-items: center; z-index: 100;
        }
        .loader { border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid var(--accent); border-radius: 50%; width: 30px; height: 30px; animation: spin 1s infinite; margin: 50px auto; }
        @keyframes spin { 100% { transform: rotate(360deg); } }

    </style>
</head>
<body>

    <div id="login-screen">
        <div class="card" style="text-align: center; max-width: 400px;">
            <h1>🔒 Cl4nk Storage</h1>
            <p style="margin: 20px 0; color: var(--text-muted);">Access Denied. Use <code>/login</code> in Telegram.</p>
        </div>
    </div>
    
    <div id="drop-zone">
        <div class="icon">📤</div>
        <h2>Drop files to upload</h2>
    </div>

    <div id="large-file-modal" class="modal-overlay">
        <div class="modal">
            <div class="icon">Tunnel 🚇</div>
            <h3>Big File Detected (>4MB)</h3>
            <p style="margin: 15px 0; color: var(--text-muted);">
                For files larger than 4MB, use the <b>Secure Tunnel</b> directly to your cloud.
            </p>
            <a href="https://t.me/Cl4nkStorageBot" target="_blank" class="btn" style="width:100%; justify-content: center;">Open Tunnel</a>
            <button class="btn btn-secondary" style="margin-top:10px; width:100%;" onclick="closeModal()">Back</button>
        </div>
    </div>

    <div class="container" id="app" style="display:none;">
        <header>
            <h1>☁️ My Drive</h1>
            <div style="display:flex; gap: 10px; align-items: center; position: relative;">
                <div id="user-info" class="meta" style="margin-right: 10px;">Loading...</div>
                
                <div style="position:relative;">
                    <button class="btn btn-secondary" onclick="toggleSortMenu()">🔃 Sort</button>
                    <div class="dropdown" id="sort-dropdown">
                        <div class="dropdown-item" onclick="setSort('name')">🔤 Name</div>
                        <div class="dropdown-item" onclick="setSort('date')">📅 Date</div>
                        <div class="dropdown-item" onclick="setSort('size')">⚖️ Size</div>
                        <div class="dropdown-item" onclick="setSort('type')">📑 Type</div>
                        <div class="dropdown-divider"></div>
                        <div class="dropdown-item" onclick="toggleSortOrder()">⬇️ Asc/Desc</div>
                    </div>
                </div>

                <button class="btn" onclick="createFolder()">➕ New Folder</button>
            </div>
        </header>

        <div class="breadcrumbs" id="breadcrumbs"></div>

        <div id="content"><div class="loader"></div></div>
    </div>

    <div id="toast">Action Successful</div>

    <script>
        let token = new URLSearchParams(window.location.search).get('token') || localStorage.getItem('cl4nk_token');
        if(token) localStorage.setItem('cl4nk_token', token);
        
        let currentFolder = 0;
        let folderHistory = [{id: 0, name: 'Home'}];
        let activeDropdown = null;
        let currentFiles = [];

        // Sort State
        let sortPref = JSON.parse(localStorage.getItem('cl4nk_sort') || '{"field":"name", "order":"asc"}');

        // Init
        document.addEventListener('click', (e) => {
            if(!e.target.closest('.actions-btn') && !e.target.closest('.dropdown') && !e.target.closest('.btn-secondary')) closeDropdown();
        });

        checkAuth();

        async function checkAuth() {
            try {
                const res = await fetch('/api/verify?token=' + token);
                const data = await res.json();
                if(data.status === 'ok') {
                    document.getElementById('login-screen').style.display = 'none';
                    document.getElementById('app').style.display = 'block';
                    document.getElementById('user-info').innerText = 'UID: ' + data.uid;
                    loadFiles(0);
                    initDragDrop();
                } else {
                    localStorage.removeItem('cl4nk_token');
                }
            } catch(e) { console.error(e); }
        }

        async function loadFiles(folderId) {
            currentFolder = folderId;
            renderBreadcrumbs();
            document.getElementById('content').innerHTML = '<div class="loader"></div>';
            
            try {
                const res = await fetch(`/api/files?token=${token}&folder=${folderId}`);
                const data = await res.json();
                currentFiles = data.files || [];
                renderGrid();
            } catch(e) {
                document.getElementById('content').innerHTML = '<p class="meta">Failed to load files.</p>';
            }
        }

        function renderGrid() {
            let files = [...currentFiles];
            const container = document.getElementById('content');
            container.innerHTML = '';
            
            if(files.length === 0) {
                container.innerHTML = '<p class="meta" style="text-align:center; padding: 50px;">Folder is empty.<br>Drag files here to upload.</p>';
                return;
            }

            // Sorting Logic
            const field = sortPref.field;
            const order = sortPref.order === 'asc' ? 1 : -1;

            files.sort((a, b) => {
                if (a.type === 'folder' && b.type !== 'folder') return -1;
                if (a.type !== 'folder' && b.type === 'folder') return 1;

                let valA = a[field] || '';
                let valB = b[field] || '';
                
                if (field === 'name') {
                    valA = valA.toLowerCase(); valB = valB.toLowerCase();
                }
                if (field === 'size' || field === 'date') {
                    valA = Number(valA) || 0; valB = Number(valB) || 0;
                }

                if (valA < valB) return -1 * order;
                if (valA > valB) return 1 * order;
                return 0;
            });

            const grid = document.createElement('div');
            grid.className = 'file-grid';

            files.forEach(f => {
                const el = document.createElement('div');
                el.className = 'card file-item';
                
                let icon = f.type === 'folder' ? '📁' : '📄';
                if(f.name.match(/\.(jpg|png|jpeg|gif)$/i)) icon = '🖼️';
                if(f.name.match(/\.(mp4|mov|avi)$/i)) icon = '🎬';

                el.innerHTML = `
                    <div class="actions-btn" onclick="toggleMenu(event, ${f.id})">⋮</div>
                    <div class="dropdown" id="menu-${f.id}">
                        <div class="dropdown-item" onclick="renameItem(${f.id}, '${f.name.replace(/'/g, "\\'")}')">✏️ Rename</div>
                        <div class="dropdown-item danger" onclick="deleteItem(${f.id})">🗑️ Delete</div>
                        ${f.type !== 'folder' ? `<div class="dropdown-item" onclick="downloadItem(${f.id})">⬇️ Download</div>` : ''}
                    </div>
                    <div onclick="clickItem(${f.id}, '${f.type}', '${f.name.replace(/'/g, "\\'")}')" style="width:100%">
                        <div class="icon">${icon}</div>
                        <div class="name" title="${f.name}">${f.name}</div>
                        <div class="meta">${formatSize(f.size || 0)}</div>
                    </div>
                `;
                grid.appendChild(el);
            });
            container.appendChild(grid);
            updateSortUI();
        }

        // --- Drag Drop & Upload ---
        function initDragDrop() {
            const dropZone = document.getElementById('drop-zone');
            
            window.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('active'); });
            window.addEventListener('dragleave', (e) => { if (e.relatedTarget === null) dropZone.classList.remove('active'); });
            window.addEventListener('drop', async (e) => {
                e.preventDefault();
                dropZone.classList.remove('active');
                
                const files = e.dataTransfer.files;
                if(files.length > 0) handleFiles(files);
            });
        }

        async function handleFiles(files) {
             // Just take the first one for now
             const file = files[0];
             
             // 4.5MB Max for Vercel Free
             if(file.size > 4.5 * 1024 * 1024) {
                 document.getElementById('large-file-modal').style.display = 'flex';
                 return;
             }
             
             // Upload
             const formData = new FormData();
             formData.append('file', file);
             formData.append('token', token);
             formData.append('parent_id', currentFolder);
             
             showToast('Uploading...', 'info');
             
             try {
                 const res = await fetch('/api/upload', {
                     method: 'POST',
                     body: formData
                 });
                 const data = await res.json();
                 if(data.status === 'ok') {
                     showToast('Upload Complete');
                     loadFiles(currentFolder);
                 } else {
                     showToast('Upload Failed: ' + data.error, 'error');
                 }
             } catch(e) {
                 showToast('Upload Error', 'error');
             }
        }

        function closeModal() {
            document.getElementById('large-file-modal').style.display = 'none';
        }

        // --- Sorting & Actions code (preserved) ---
        function toggleSortMenu() {
            closeDropdown();
            document.getElementById('sort-dropdown').classList.add('show');
            activeDropdown = 'sort-dropdown';
        }

        function setSort(field) { sortPref.field = field; saveSort(); renderGrid(); }
        function toggleSortOrder() { sortPref.order = sortPref.order === 'asc' ? 'desc' : 'asc'; saveSort(); renderGrid(); }
        function saveSort() { localStorage.setItem('cl4nk_sort', JSON.stringify(sortPref)); closeDropdown(); }
        function updateSortUI() {}

        function toggleMenu(e, id) {
            e.stopPropagation();
            closeDropdown();
            const menu = document.getElementById(`menu-${id}`);
            menu.classList.add('show');
            e.target.classList.add('active');
            activeDropdown = id;
        }

        function closeDropdown() {
            document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('show'));
            document.querySelectorAll('.actions-btn').forEach(b => b.classList.remove('active'));
            activeDropdown = null;
        }

        function clickItem(id, type, name) {
            if(type === 'folder') {
                folderHistory.push({id: id, name: name});
                loadFiles(id);
            } else { downloadItem(id); }
        }
        
        function downloadItem(id) { window.open(`/api/download/${id}?token=${token}`, '_blank'); }

        async function createFolder() {
            const name = prompt("Folder Name:");
            if(!name) return;
            await apiAction('mkdir', { name: name, parent_id: currentFolder });
        }

        async function renameItem(id, oldName) {
            const name = prompt("New Name:", oldName);
            if(!name || name === oldName) return;
            await apiAction('rename', { id: id, name: name });
        }

        async function deleteItem(id) {
            if(!confirm("Are you sure you want to delete this item?")) return;
            await apiAction('delete', { id: id });
        }

        async function apiAction(action, payload) {
            try {
                const res = await fetch('/api/action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ token, action, ...payload })
                });
                const data = await res.json();
                if(data.error) alert(data.error);
                else { showToast('Success'); loadFiles(currentFolder); }
            } catch(e) { alert("Action failed"); }
        }

        function renderBreadcrumbs() {
            const el = document.getElementById('breadcrumbs');
            el.innerHTML = '';
            folderHistory.forEach((f, index) => {
                const span = document.createElement('span');
                span.className = 'breadcrumb-item';
                span.innerText = f.name;
                span.onclick = () => { folderHistory = folderHistory.slice(0, index + 1); loadFiles(f.id); };
                el.appendChild(span);
                if(index < folderHistory.length - 1) el.appendChild(document.createTextNode(' / '));
            });
        }

        function formatSize(bytes) {
            if(bytes === 0) return '';
            const units = ['B', 'KB', 'MB', 'GB'];
            let i = 0;
            while(bytes > 1024 && i < units.length - 1) { bytes /= 1024; i++; }
            return bytes.toFixed(1) + ' ' + units[i];
        }

        function showToast(msg, type='success') {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.className = type === 'error' ? 'show toast-error' : 'show';
            setTimeout(() => t.className = '', 3000);
        }

    </script>
</body>
</html>
"""
