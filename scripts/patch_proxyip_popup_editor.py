from pathlib import Path

path = Path('_worker.js')
s = path.read_text(encoding='utf-8')
original = s

# 1) Persist first V2 migration immediately so generated node IDs are stable before the first edit.
old = r'''\treturn {
\t\tversion: 2,
\t\tupdatedAt: 0,
\t\tnodes: lines.map(line => ({ id: 生成自定义ProxyIP节点ID(), line, proxyip: legacy[line] || '' })),
\t};
}'''
new = r'''\tconst migrated = {
\t\tversion: 2,
\t\tupdatedAt: Date.now(),
\t\tnodes: lines.map(line => ({ id: 生成自定义ProxyIP节点ID(), line, proxyip: legacy[line] || '' })),
\t};
\ttry { await env.KV.put(自定义ProxyIP节点V2KV键, JSON.stringify(migrated, null, 2)); }
\tcatch (error) { log(`[ProxyIP节点] 首次 V2 迁移持久化失败: ${error?.message || error}`); }
\treturn migrated;
}'''
if old not in s:
    raise SystemExit('migration return block not found')
s = s.replace(old, new, 1)

# 2) GET endpoint now exposes stable IDs to the admin popup.
old = r'''\t\t\t\t\tif (访问路径 === 'admin/proxyip-nodes.json' && request.method === 'GET') {
\t\t\t\t\t\tconst 节点映射 = await 读取自定义ProxyIP节点映射(env);
\t\t\t\t\t\tconst nodes = Object.entries(节点映射).map(([line, proxyip]) => ({ line, proxyip }));
\t\t\t\t\t\treturn new Response(JSON.stringify({ success: true, nodes }, null, 2), { status: 200, headers: { 'Content-Type': 'application/json;charset=utf-8', 'Cache-Control': 'no-store' } });
\t\t\t\t\t}'''
new = r'''\t\t\t\t\tif (访问路径 === 'admin/proxyip-nodes.json' && request.method === 'GET') {
\t\t\t\t\t\tconst 状态 = await 读取自定义ProxyIP节点记录(env);
\t\t\t\t\t\tconst nodes = 状态.nodes.map(item => ({ id: item.id, line: item.line, proxyip: item.proxyip || '' }));
\t\t\t\t\t\treturn new Response(JSON.stringify({ success: true, version: 2, updatedAt: 状态.updatedAt || 0, nodes }, null, 2), { status: 200, headers: { 'Content-Type': 'application/json;charset=utf-8', 'Cache-Control': 'no-store' } });
\t\t\t\t\t}'''
if old not in s:
    raise SystemExit('proxyip GET endpoint not found')
s = s.replace(old, new, 1)

# 3) Add exact-by-ID update endpoint before ordinary config POST routes.
anchor = r'''\t\t\t\t\t} else if (request.method === 'POST') {// 处理 KV 操作（POST 请求）
\t\t\t\t\t\tif (访问路径 === 'admin/config.json') { // 保存config.json配置'''
replacement = r'''\t\t\t\t\t} else if (request.method === 'POST') {// 处理 KV 操作（POST 请求）
\t\t\t\t\t\tif (访问路径 === 'admin/proxyip-nodes/update') { // 按稳定 ID 精确编辑 ProxyIP 节点
\t\t\t\t\t\t\ttry {
\t\t\t\t\t\t\t\tconst input = await request.json();
\t\t\t\t\t\t\t\tconst id = String(input?.id || '').trim();
\t\t\t\t\t\t\t\tif (!id) return new Response(JSON.stringify({ error: '缺少节点 ID' }), { status: 400, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t\tconst 节点名称 = String(input?.name || '').replace(/[\\r\\n]+/g, ' ').trim();
\t\t\t\t\t\t\t\tif (!节点名称) return new Response(JSON.stringify({ error: '节点名称不能为空' }), { status: 400, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t\tif (节点名称.length > 120) return new Response(JSON.stringify({ error: '节点名称不能超过 120 个字符' }), { status: 400, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t\tconst 优选主机 = 规范化优选节点主机(input?.host);
\t\t\t\t\t\t\t\tconst 优选端口 = Number(String(input?.port || '443').trim());
\t\t\t\t\t\t\t\tif (!Number.isInteger(优选端口) || 优选端口 < 1 || 优选端口 > 65535) throw new Error('优选端口必须为 1~65535');
\t\t\t\t\t\t\t\tconst ProxyIP = 规范化ProxyIP端点(input?.proxyip);
\t\t\t\t\t\t\t\tconst 新行 = 规范化自定义优选行(`${优选主机}:${优选端口}#${节点名称}`);
\n\t\t\t\t\t\t\t\tconst 状态 = await 读取自定义ProxyIP节点记录(env);
\t\t\t\t\t\t\t\tconst index = 状态.nodes.findIndex(item => String(item.id) === id);
\t\t\t\t\t\t\t\tif (index < 0) return new Response(JSON.stringify({ error: '节点不存在或已被删除，请重新打开编辑窗口' }), { status: 404, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t\tif (状态.nodes.some((item, i) => i !== index && 规范化自定义优选行(item.line) === 新行)) {
\t\t\t\t\t\t\t\t\treturn new Response(JSON.stringify({ error: '修改后会与另一条节点完全重复，请调整节点名称' }), { status: 409, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t\t}
\n\t\t\t\t\t\t\t\tconst 旧行 = 规范化自定义优选行(状态.nodes[index].line);
\t\t\t\t\t\t\t\t状态.nodes[index] = { ...状态.nodes[index], id, line: 新行, proxyip: ProxyIP };
\t\t\t\t\t\t\t\tconst 当前文本 = await env.KV.get('ADD.txt') || '';
\t\t\t\t\t\t\t\tconst 当前行列表 = 当前文本.split(/\\r?\\n/).map(规范化自定义优选行).filter(Boolean);
\t\t\t\t\t\t\t\tlet 已替换 = false;
\t\t\t\t\t\t\t\tconst 新行列表 = 当前行列表.map(line => {
\t\t\t\t\t\t\t\t\tif (!已替换 && line === 旧行) { 已替换 = true; return 新行; }
\t\t\t\t\t\t\t\t\treturn line;
\t\t\t\t\t\t\t\t});
\t\t\t\t\t\t\t\tif (!已替换) 新行列表.push(新行);
\n\t\t\t\t\t\t\t\tconst 更新时间 = Date.now();
\t\t\t\t\t\t\t\tconst V2状态 = { version: 2, updatedAt: 更新时间, nodes: 状态.nodes };
\t\t\t\t\t\t\t\tconst 兼容旧映射 = {};
\t\t\t\t\t\t\t\tfor (const item of 状态.nodes) if (item.proxyip) 兼容旧映射[规范化自定义优选行(item.line)] = item.proxyip;
\t\t\t\t\t\t\t\tconst 新文本 = 新行列表.join('\\n');
\t\t\t\t\t\t\t\tawait Promise.all([
\t\t\t\t\t\t\t\t\tenv.KV.put('ADD.txt', 新文本),
\t\t\t\t\t\t\t\t\tenv.KV.put(自定义ProxyIP节点V2KV键, JSON.stringify(V2状态, null, 2)),
\t\t\t\t\t\t\t\t\tenv.KV.put(自定义ProxyIP节点KV键, JSON.stringify(兼容旧映射, null, 2)),
\t\t\t\t\t\t\t\t]);
\t\t\t\t\t\t\t\tctx.waitUntil(请求日志记录(env, request, 访问IP, 'Update_ProxyIP_Node', config_JSON));
\t\t\t\t\t\t\t\treturn new Response(JSON.stringify({ success: true, message: 'ProxyIP 节点已更新', id, line: 新行, proxyip: ProxyIP, customIPs: 新文本, updatedAt: 更新时间 }), { status: 200, headers: { 'Content-Type': 'application/json;charset=utf-8', 'Cache-Control': 'no-store' } });
\t\t\t\t\t\t\t} catch (error) {
\t\t\t\t\t\t\t\tconsole.error('更新 ProxyIP 节点失败:', error);
\t\t\t\t\t\t\t\treturn new Response(JSON.stringify({ error: '更新 ProxyIP 节点失败: ' + error.message }), { status: 500, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t}
\t\t\t\t\t\t} else if (访问路径 === 'admin/config.json') { // 保存config.json配置'''
if anchor not in s:
    raise SystemExit('POST route anchor not found')
s = s.replace(anchor, replacement, 1)

# 4) Popup HTML: existing-node selector + dynamic title/hint.
s = s.replace(
    '<h2 class="api-optimize-modal-title">添加 ProxyIP 节点</h2>',
    '<h2 class="api-optimize-modal-title" id="proxyIpModalTitle">ProxyIP 节点</h2>',
    1,
)
form_anchor = r'''\t\t<div class="api-form-group chain-proxy-form">
\t\t\t<div class="api-form-row-item">
\t\t\t\t<label for="proxyIpNodeName">节点名称:</label>'''
form_replacement = r'''\t\t<div class="api-form-group chain-proxy-form">
\t\t\t<div class="api-form-row-item">
\t\t\t\t<label for="proxyIpExistingNode">已有节点:</label>
\t\t\t\t<select id="proxyIpExistingNode" title="选择已有 ProxyIP 节点" onchange="selectProxyIpNode(this.value)">
\t\t\t\t\t<option value="">＋ 新增 ProxyIP 节点</option>
\t\t\t\t</select>
\t\t\t</div>
\t\t\t<div class="api-form-row-item">
\t\t\t\t<label for="proxyIpNodeName">节点名称:</label>'''
if form_anchor not in s:
    raise SystemExit('popup form anchor not found')
s = s.replace(form_anchor, form_replacement, 1)
s = s.replace(
    '<p class="proxyip-save-hint">填写节点信息后可直接添加。点击“可用性验证”会在新选项卡调用独立 VPS 上的 ProxyIP Scanner，并自动带入当前 ProxyIP；检测结果不影响添加。添加后点击原页面“保存”才正式生效。</p>',
    '<p class="proxyip-save-hint" id="proxyIpSaveHint">新增节点填写后点击“添加”，再点击原页面“保存”生效；编辑已有节点时点击“保存修改”会按内部节点 ID 直接保存，不需要删除重建。</p>',
    1,
)

# Add select styling beside current popup styles.
css_anchor = '#proxyIpNodeModal .proxyip-address-wrap input{flex:1;min-width:0}'
css_replacement = css_anchor + '\n#proxyIpNodeModal select{width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px;background:var(--input-bg,#fff);color:inherit}'
if css_anchor not in s:
    raise SystemExit('popup CSS anchor not found')
s = s.replace(css_anchor, css_replacement, 1)

# 5) Frontend state tracks stable node IDs returned by the GET endpoint.
state_anchor = r'''\tconst nativeFetch = window.fetch.bind(window);
\tlet persistedReady = Promise.resolve();'''
state_replacement = r'''\tconst nativeFetch = window.fetch.bind(window);
\tlet persistedReady = Promise.resolve();
\tlet persistedNodes = [];
\tlet editingNodeId = '';'''
if state_anchor not in s:
    raise SystemExit('frontend state anchor not found')
s = s.replace(state_anchor, state_replacement, 1)

# Helpers for parsing a visible line and populating edit mode.
helper_anchor = r'''\tfunction cleanLines(value){
\t\treturn String(value || '').split(/\\r?\\n/).map(canonicalLine).filter(Boolean);
\t}
\tfunction normalizeHost(value){'''
helper_replacement = r'''\tfunction cleanLines(value){
\t\treturn String(value || '').split(/\\r?\\n/).map(canonicalLine).filter(Boolean);
\t}
\tfunction splitPreferredLine(value){
\t\tconst line = canonicalLine(value);
\t\tconst hash = line.indexOf('#');
\t\tconst address = (hash < 0 ? line : line.slice(0, hash)).trim();
\t\tconst name = hash < 0 ? '' : line.slice(hash + 1).trim();
\t\tlet host = address, port = '443';
\t\tif (address.startsWith('[')) {
\t\t\tconst close = address.indexOf(']');
\t\t\tif (close >= 0) {
\t\t\t\thost = address.slice(0, close + 1);
\t\t\t\tif (address[close + 1] === ':' && /^\\d+$/.test(address.slice(close + 2))) port = address.slice(close + 2);
\t\t\t}
\t\t} else {
\t\t\tconst colon = address.lastIndexOf(':');
\t\t\tif (colon > 0 && /^\\d+$/.test(address.slice(colon + 1))) { host = address.slice(0, colon); port = address.slice(colon + 1); }
\t\t}
\t\treturn { line, host, port, name };
\t}
\tfunction renderExistingNodeOptions(){
\t\tconst select = document.getElementById('proxyIpExistingNode');
\t\tif (!select) return;
\t\tselect.innerHTML = '<option value="">＋ 新增 ProxyIP 节点</option>';
\t\tfor (const item of persistedNodes.filter(v => v && v.id && v.proxyip)) {
\t\t\tconst option = document.createElement('option');
\t\t\toption.value = String(item.id);
\t\t\toption.textContent = String(item.line || '') + '  →  ' + String(item.proxyip || '');
\t\t\tselect.appendChild(option);
\t\t}
\t\tselect.value = editingNodeId || '';
\t}
\tfunction setEditorMode(node){
\t\tconst title = document.getElementById('proxyIpModalTitle');
\t\tconst hint = document.getElementById('proxyIpSaveHint');
\t\tconst button = document.getElementById('btnAddProxyIp');
\t\tconst hostInput = document.getElementById('proxyIpPreferredHost');
\t\tconst portInput = document.getElementById('proxyIpPreferredPort');
\t\tconst nameInput = document.getElementById('proxyIpNodeName');
\t\tconst proxyInput = document.getElementById('proxyIpAddress');
\t\tif (node) {
\t\t\teditingNodeId = String(node.id || '');
\t\t\tconst parsed = splitPreferredLine(node.line);
\t\t\tif (hostInput) hostInput.value = parsed.host;
\t\t\tif (portInput) portInput.value = parsed.port;
\t\t\tif (nameInput) nameInput.value = parsed.name;
\t\t\tif (proxyInput) proxyInput.value = String(node.proxyip || '');
\t\t\tif (title) title.textContent = '编辑 ProxyIP 节点';
\t\t\tif (button) button.textContent = '保存修改';
\t\t\tif (hint) hint.textContent = '当前按内部稳定节点 ID 编辑。优选 IP、端口、节点名称、ProxyIP 都可以单独修改，其他字段不会因为修改而丢失绑定。';
\t\t} else {
\t\t\teditingNodeId = '';
\t\t\tif (nameInput) nameInput.value = '';
\t\t\tif (proxyInput) proxyInput.value = '';
\t\t\tif (portInput) portInput.value = '443';
\t\t\tif (hostInput) {
\t\t\t\tlet def = '';
\t\t\t\ttry { if (typeof getDefaultChainProxyHost === 'function') def = getDefaultChainProxyHost(); } catch (_) {}
\t\t\t\thostInput.value = def || String(window.location.hostname || '');
\t\t\t}
\t\t\tif (title) title.textContent = '添加 ProxyIP 节点';
\t\t\tif (button) button.textContent = '添加';
\t\t\tif (hint) hint.textContent = '新增节点填写后点击“添加”，再点击原页面“保存”正式生效。已有节点请从上方下拉框选择后直接修改。';
\t\t}
\t\trenderExistingNodeOptions();
\t}
\twindow.selectProxyIpNode = function(id){
\t\tconst node = persistedNodes.find(item => String(item?.id || '') === String(id || '')) || null;
\t\tsetEditorMode(node);
\t};
\tfunction normalizeHost(value){'''
if helper_anchor not in s:
    raise SystemExit('frontend helper anchor not found')
s = s.replace(helper_anchor, helper_replacement, 1)

# loadPersisted now retains IDs and all V2 node metadata.
old = r'''\t\t\tconst d = await r.json();
\t\t\tfor (const k of Object.keys(persisted)) delete persisted[k];
\t\t\tfor (const item of (Array.isArray(d.nodes) ? d.nodes : [])) {
\t\t\t\tif (item && item.line && item.proxyip) persisted[canonicalLine(item.line)] = String(item.proxyip).trim();
\t\t\t}
\t\t} catch (_) {}'''
new = r'''\t\t\tconst d = await r.json();
\t\t\tpersistedNodes = Array.isArray(d.nodes) ? d.nodes.map(item => ({ id: String(item?.id || ''), line: canonicalLine(item?.line), proxyip: String(item?.proxyip || '').trim() })).filter(item => item.line) : [];
\t\t\tfor (const k of Object.keys(persisted)) delete persisted[k];
\t\t\tfor (const item of persistedNodes) {
\t\t\t\tif (item.line && item.proxyip) persisted[item.line] = item.proxyip;
\t\t\t}
\t\t\trenderExistingNodeOptions();
\t\t} catch (_) {}'''
if old not in s:
    raise SystemExit('loadPersisted block not found')
s = s.replace(old, new, 1)

# Open popup fresh each time so an existing record can be selected reliably.
start = s.index(r'''\twindow.openProxyIpModal = function(){''')
end = s.index(r'''\twindow.closeProxyIpModal = function()''', start)
new_open = r'''\twindow.openProxyIpModal = async function(){
\t\tconst modal = document.getElementById('proxyIpNodeModal');
\t\tif (!modal) return;
\t\ttry { await persistedReady; await loadPersisted(); } catch (_) {}
\t\tsetEditorMode(null);
\t\tmodal.classList.add('show');
\t\tsetTimeout(function(){ document.getElementById('proxyIpExistingNode')?.focus(); }, 0);
\t};
'''
s = s[:start] + new_open + s[end:]

# Add/update action: edit mode uses the exact ID endpoint; add mode keeps the established flow.
start = s.index(r'''\twindow.addProxyIpNode = function(){''')
end = s.index(r'''\n\n\tconst chainBtn = document.getElementById('chainProxyBtn');''', start)
new_action = r'''\twindow.addProxyIpNode = async function(){
\t\tconst button = document.getElementById('btnAddProxyIp');
\t\ttry {
\t\t\tconst name = String(document.getElementById('proxyIpNodeName')?.value || '').replace(/[\\r\\n]+/g, ' ').trim();
\t\t\tif (!name) throw new Error('请输入节点名称');
\t\t\tif (name.length > 120) throw new Error('节点名称不能超过 120 个字符');
\t\t\tconst host = normalizeHost(document.getElementById('proxyIpPreferredHost')?.value);
\t\t\tconst port = Number(String(document.getElementById('proxyIpPreferredPort')?.value || '443').trim());
\t\t\tif (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('优选端口必须为 1~65535');
\t\t\tconst proxyip = normalizeProxy(document.getElementById('proxyIpAddress')?.value);
\t\t\tconst line = host + ':' + port + '#' + name;
\t\t\tconst textarea = document.getElementById('customIPs');
\t\t\tif (!textarea) throw new Error('未找到自定义优选地址输入框');
\n\t\t\tif (editingNodeId) {
\t\t\t\tif (button) { button.disabled = true; button.textContent = '保存中…'; }
\t\t\t\tconst response = await nativeFetch('/admin/proxyip-nodes/update', {
\t\t\t\t\tmethod: 'POST',
\t\t\t\t\theaders: { 'Content-Type': 'application/json;charset=utf-8' },
\t\t\t\t\tbody: JSON.stringify({ id: editingNodeId, host, port, name, proxyip }),
\t\t\t\t});
\t\t\t\tlet data = {};
\t\t\t\ttry { data = await response.json(); } catch (_) {}
\t\t\t\tif (!response.ok) throw new Error(data.error || ('保存失败：HTTP ' + response.status));
\t\t\t\ttextarea.value = String(data.customIPs || textarea.value);
\t\t\t\tif (textarea._refreshLineEditor) textarea._refreshLineEditor();
\t\t\t\ttextarea.dispatchEvent(new Event('input', { bubbles: true }));
\t\t\t\tfor (const k of Object.keys(pending)) delete pending[k];
\t\t\t\tawait loadPersisted();
\t\t\t\twindow.closeProxyIpModal();
\t\t\t\tif (typeof showToast === 'function') showToast('✅ ProxyIP 节点已精确更新并保存', 'success');
\t\t\t\treturn;
\t\t\t}
\n\t\t\tconst lines = cleanLines(textarea.value);
\t\t\tif (!lines.includes(line)) lines.push(line);
\t\t\ttextarea.value = lines.join('\\n');
\t\t\tpending[canonicalLine(line)] = proxyip;
\t\t\tif (textarea._refreshLineEditor) textarea._refreshLineEditor();
\t\t\ttry { if (typeof markModified === 'function') markModified('sub'); } catch (_) {}
\t\t\ttextarea.dispatchEvent(new Event('input', { bubbles: true }));
\t\t\twindow.closeProxyIpModal();
\t\t\tif (typeof showToast === 'function') showToast('✅ ProxyIP 节点已追加，请点击“保存”后生效', 'success');
\t\t} catch (error) {
\t\t\tif (typeof showToast === 'function') showToast(error.message || String(error), 'error');
\t\t\telse alert(error.message || String(error));
\t\t} finally {
\t\t\tif (button) { button.disabled = false; button.textContent = editingNodeId ? '保存修改' : '添加'; }
\t\t}
\t};'''
s = s[:start] + new_action + s[end:]

required = [
    "访问路径 === 'admin/proxyip-nodes/update'",
    "id=\"proxyIpExistingNode\"",
    "let editingNodeId = '';",
    "button.textContent = '保存修改'",
    "await nativeFetch('/admin/proxyip-nodes/update'",
    "const nodes = 状态.nodes.map(item => ({ id: item.id",
    "首次 V2 迁移持久化失败",
]
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit('post-patch assertions failed: ' + repr(missing))
if s == original:
    raise SystemExit('no changes produced')

path.write_text(s, encoding='utf-8')
