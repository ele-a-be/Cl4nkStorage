
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
            --text: #e2e8f0;
            --text-muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
        body { background: var(--bg); color: var(--text); min-height: 100vh; overflow-x: hidden; }
        
        /* Layout */
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { 
            display: flex; justify-content: space-between; align-items: center; 
            padding: 20px 0; margin-bottom: 30px;
            border-bottom: 1px solid var(--glass-border);
        }
        h1 { font-weight: 600; font-size: 1.5rem; display: flex; align-items: center; gap: 10px; }
        
        /* Glass Cards */
        .card {
            background: var(--glass);
            backdrop-filter: blur(10px);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .file-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
        }
        .file-item {
            display: flex; flex-direction: column; align-items: center; text-align: center;
            cursor: pointer; position: relative;
        }
        .file-item:hover { transform: translateY(-3px); background: rgba(255,255,255,0.05); }
        .icon { font-size: 3rem; margin-bottom: 10px; }
        .name { font-size: 0.9rem; word-break: break-word; line-height: 1.2; max-width: 100%; }
        .meta { font-size: 0.7rem; color: var(--text-muted); margin-top: 5px; }

        /* Navigation / Breadcrumbs */
        .breadcrumbs { display: flex; gap: 10px; margin-bottom: 20px; color: var(--accent); cursor: pointer; }
        .breadcrumb-item:hover { text-decoration: underline; }

        /* Loader */
        .loader { 
            border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid var(--accent); 
            border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 50px auto; 
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        /* Login Screen */
        #login-screen { 
            position: fixed; top:0; left:0; width:100%; height:100%; 
            background: var(--bg); display: flex; justify-content: center; align-items: center; z-index: 100;
        }
        .login-box { text-align: center; max-width: 400px; }
        
        /* Notifications */
        .toast {
            position: fixed; bottom: 20px; right: 20px;
            background: #10b981; color: white; padding: 10px 20px; border-radius: 8px;
            transform: translateY(100px); transition: transform 0.3s;
        }
        .toast.show { transform: translateY(0); }
        .toast.error { background: #ef4444; }

    </style>
</head>
<body>

    <div id="login-screen">
        <div class="login-box card">
            <h1>🔒 Cl4nk Storage</h1>
            <p style="margin: 20px 0; color: var(--text-muted);">Access Denied.</p>
            <p>Please use <code>/login</code> in the Telegram Bot to get an access link.</p>
        </div>
    </div>

    <div class="container" id="app" style="display:none;">
        <header>
            <h1>☁️ My Drive</h1>
            <div id="user-info" class="meta">Loading...</div>
        </header>

        <div class="breadcrumbs" id="breadcrumbs"></div>

        <div id="content">
            <div class="loader"></div>
        </div>
    </div>

    <div id="toast" class="toast">Action Successful</div>

    <script>
        // State
        let token = new URLSearchParams(window.location.search).get('token');
        let currentFolder = 0;
        let folderHistory = [{id: 0, name: 'Home'}];
        let filesData = [];

        // Init
        if(token) {
            localStorage.setItem('cl4nk_token', token);
        } else {
            token = localStorage.getItem('cl4nk_token');
        }

        if(token) {
            checkAuth();
        }

        async function checkAuth() {
            try {
                const res = await fetch('/api/verify?token=' + token);
                if(res.ok) {
                    document.getElementById('login-screen').style.display = 'none';
                    document.getElementById('app').style.display = 'block';
                    loadFiles(0);
                } else {
                    localStorage.removeItem('cl4nk_token');
                    showToast('Session Expired', true);
                }
            } catch(e) {
                showToast('Connection Error', true);
            }
        }

        async function loadFiles(folderId) {
            currentFolder = folderId;
            renderBreadcrumbs();
            document.getElementById('content').innerHTML = '<div class="loader"></div>';
            
            try {
                const res = await fetch(`/api/files?token=${token}&folder=${folderId}`);
                const data = await res.json();
                filesData = data.files;
                renderGrid(filesData);
            } catch(e) {
                document.getElementById('content').innerHTML = '<p class="meta">Failed to load files.</p>';
            }
        }

        function renderGrid(files) {
            const container = document.getElementById('content');
            container.innerHTML = '';
            
            if(files.length === 0) {
                container.innerHTML = '<p class="meta" style="text-align:center; padding: 50px;">Folder is empty.</p>';
                return;
            }

            const grid = document.createElement('div');
            grid.className = 'file-grid';

            // Sort: Folders first
            files.sort((a,b) => (a.type === 'folder' ? -1 : 1));

            files.forEach(f => {
                const el = document.createElement('div');
                el.className = 'card file-item';
                el.onclick = () => handleItemClick(f);
                
                let icon = f.type === 'folder' ? '📁' : '📄';
                if(f.name.endsWith('.jpg') || f.name.endsWith('.png')) icon = '🖼️';
                if(f.name.endsWith('.mp4')) icon = '🎬';

                el.innerHTML = `
                    <div class="icon">${icon}</div>
                    <div class="name">${f.name}</div>
                    <div class="meta">${formatSize(f.size || 0)}</div>
                `;
                grid.appendChild(el);
            });
            container.appendChild(grid);
        }

        function handleItemClick(item) {
            if(item.type === 'folder') {
                folderHistory.push({id: item.id, name: item.name});
                loadFiles(item.id);
            } else {
                // Download
                window.open(`/api/download/${item.id}?token=${token}`, '_blank');
            }
        }

        function renderBreadcrumbs() {
            const el = document.getElementById('breadcrumbs');
            el.innerHTML = '';
            folderHistory.forEach((f, index) => {
                const span = document.createElement('span');
                span.className = 'breadcrumb-item';
                span.innerText = f.name;
                span.onclick = () => {
                    folderHistory = folderHistory.slice(0, index + 1);
                    loadFiles(f.id);
                };
                el.appendChild(span);
                if(index < folderHistory.length - 1) {
                    el.appendChild(document.createTextNode(' / '));
                }
            });
        }

        function formatSize(bytes) {
            if(bytes === 0) return '';
            const units = ['B', 'KB', 'MB', 'GB'];
            let i = 0;
            while(bytes > 1024 && i < units.length - 1) {
                bytes /= 1024;
                i++;
            }
            return bytes.toFixed(1) + ' ' + units[i];
        }

        function showToast(msg, isError) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.className = 'toast show' + (isError ? ' error' : '');
            setTimeout(() => t.className = 'toast', 3000);
        }

    </script>
</body>
</html>
"""
