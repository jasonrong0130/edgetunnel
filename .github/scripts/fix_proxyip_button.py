from pathlib import Path

p = Path('_worker.js')
text = p.read_text(encoding='utf-8-sig')

old = """\t\tif (html.includes('id=\"proxyIpNodeBtn\"') || !html.includes('id=\"chainProxyBtn\"')) {
\t\t\tconst headers = new Headers(response.headers);
\t\t\theaders.delete('content-length'); headers.delete('content-encoding'); headers.set('Cache-Control', 'no-store');
\t\t\treturn new Response(html, { status: response.status, statusText: response.statusText, headers });
\t\t}

\t\tconst proxyButton = '<button type=\"button\" class=\"btn btn-chain-proxy hidden-section proxyip-node-btn\" id=\"proxyIpNodeBtn\" onclick=\"openProxyIpModal()\">ProxyIP节点</button>';
\t\tconst chainButtonPattern = /(<button\\s+type=\"button\"\\s+class=\"btn btn-chain-proxy hidden-section\"\\s+id=\"chainProxyBtn\"[\\s\\S]*?<\\/button>)/i;
\t\tlet body = html.replace(chainButtonPattern, '$1\\n\\t\\t\\t\\t\\t\\t' + proxyButton);
"""
new = """\t\tif (html.includes('data-custom-proxyip-ui=\"1\"')) {
\t\t\tconst headers = new Headers(response.headers);
\t\t\theaders.delete('content-length'); headers.delete('content-encoding'); headers.set('Cache-Control', 'no-store');
\t\t\treturn new Response(html, { status: response.status, statusText: response.statusText, headers });
\t\t}

\t\tlet body = html;
"""
if old not in text:
    raise SystemExit('server-side button injection block not found')
text = text.replace(old, new, 1)

old_sync = """\tfunction syncButton(){
\t\tconst source = document.getElementById('chainProxyBtn');
\t\tconst btn = document.getElementById('proxyIpNodeBtn');
\t\tif (!source || !btn) return;
\t\tbtn.classList.toggle('hidden-section', source.classList.contains('hidden-section'));
\t\tbtn.style.display = source.style.display || '';
\t\trequestAnimationFrame(function(){
\t\t\tconst w = source.getBoundingClientRect().width;
\t\t\tif (w > 0) btn.style.width = w + 'px';
\t\t});
\t}
"""
new_sync = """\tfunction ensureButton(){
\t\tconst source = document.getElementById('chainProxyBtn');
\t\tif (!source) return null;
\t\tlet btn = document.getElementById('proxyIpNodeBtn');
\t\tif (!btn) {
\t\t\tbtn = document.createElement('button');
\t\t\tbtn.type = 'button';
\t\t\tbtn.className = 'btn btn-chain-proxy hidden-section proxyip-node-btn';
\t\t\tbtn.id = 'proxyIpNodeBtn';
\t\t\tbtn.textContent = 'ProxyIP节点';
\t\t\tbtn.addEventListener('click', function(){ window.openProxyIpModal(); });
\t\t\tsource.insertAdjacentElement('afterend', btn);
\t\t}
\t\treturn btn;
\t}
\tfunction syncButton(){
\t\tconst source = document.getElementById('chainProxyBtn');
\t\tconst btn = ensureButton();
\t\tif (!source || !btn) return;
\t\tbtn.classList.toggle('hidden-section', source.classList.contains('hidden-section'));
\t\tbtn.style.display = source.style.display || '';
\t\trequestAnimationFrame(function(){
\t\t\tconst w = source.getBoundingClientRect().width;
\t\t\tif (w > 0) btn.style.width = w + 'px';
\t\t});
\t}
"""
if old_sync not in text:
    raise SystemExit('syncButton block not found')
text = text.replace(old_sync, new_sync, 1)

old_tail = """\tconst chainBtn = document.getElementById('chainProxyBtn');
\tif (chainBtn) new MutationObserver(syncButton).observe(chainBtn, { attributes: true, attributeFilter: ['class','style'] });
\tdocument.getElementById('ipMode')?.addEventListener('change', function(){ setTimeout(syncButton, 0); });
\twindow.addEventListener('resize', syncButton);
\tloadPersisted();
\tsyncButton();
"""
new_tail = """\tconst chainBtn = document.getElementById('chainProxyBtn');
\tensureButton();
\tif (chainBtn) new MutationObserver(syncButton).observe(chainBtn, { attributes: true, attributeFilter: ['class','style'] });
\tdocument.getElementById('ipMode')?.addEventListener('change', function(){ setTimeout(syncButton, 0); });
\twindow.addEventListener('resize', syncButton);
\tloadPersisted();
\tsyncButton();
"""
if old_tail not in text:
    raise SystemExit('ProxyIP init tail not found')
text = text.replace(old_tail, new_tail, 1)

p.write_text(text, encoding='utf-8')
