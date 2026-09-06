from pathlib import Path

path = Path('_worker.js')
s = path.read_text(encoding='utf-8')
original = s


def replace_once(old: str, new: str, label: str):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, 1)


# 1) Persist the first V2 migration immediately so node IDs stay stable before any edit.
replace_once(
    "\treturn {\n\t\tversion: 2,\n\t\tupdatedAt: 0,\n\t\tnodes: lines.map(line => ({ id: 生成自定义ProxyIP节点ID(), line, proxyip: legacy[line] || '' })),\n\t};\n}",
    "\tconst migrated = {\n\t\tversion: 2,\n\t\tupdatedAt: Date.now(),\n\t\tnodes: lines.map(line => ({ id: 生成自定义ProxyIP节点ID(), line, proxyip: legacy[line] || '' })),\n\t};\n\ttry { await env.KV.put(自定义ProxyIP节点V2KV键, JSON.stringify(migrated, null, 2)); }\n\tcatch (error) { log(`[ProxyIP节点] 首次 V2 迁移持久化失败: ${error?.message || error}`); }\n\treturn migrated;\n}",
    'migration block',
)

# 2) GET returns V2 records including stable IDs.
replace_once(
    "\t\t\t\t\tif (访问路径 === 'admin/proxyip-nodes.json' && request.method === 'GET') {\n\t\t\t\t\t\tconst 节点映射 = await 读取自定义ProxyIP节点映射(env);\n\t\t\t\t\t\tconst nodes = Object.entries(节点映射).map(([line, proxyip]) => ({ line, proxyip }));\n\t\t\t\t\t\treturn new Response(JSON.stringify({ success: true, nodes }, null, 2), { status: 200, headers: { 'Content-Type': 'application/json;charset=utf-8', 'Cache-Control': 'no-store' } });\n\t\t\t\t\t}",
    "\t\t\t\t\tif (访问路径 === 'admin/proxyip-nodes.json' && request.method === 'GET') {\n\t\t\t\t\t\tconst 状态 = await 读取自定义ProxyIP节点记录(env);\n\t\t\t\t\t\tconst nodes = 状态.nodes.map(item => ({ id: item.id, line: item.line, proxyip: item.proxyip || '' }));\n\t\t\t\t\t\treturn new Response(JSON.stringify({ success: true, version: 2, updatedAt: 状态.updatedAt || 0, nodes }, null, 2), { status: 200, headers: { 'Content-Type': 'application/json;charset=utf-8', 'Cache-Control': 'no-store' } });\n\t\t\t\t\t}",
    'GET proxyip nodes endpoint',
)

# 3) Add exact update-by-ID route before config POST.
anchor = "\t\t\t\t\t} else if (request.method === 'POST') {// 处理 KV 操作（POST 请求）\n\t\t\t\t\t\tif (访问路径 === 'admin/config.json') { // 保存config.json配置"
if anchor not in s:
    raise SystemExit('POST route anchor not found')
update_route = """\t\t\t\t\t} else if (request.method === 'POST') {// 处理 KV 操作（POST 请求）
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

\t\t\t\t\t\t\t\tconst 状态 = await 读取自定义ProxyIP节点记录(env);
\t\t\t\t\t\t\t\tconst index = 状态.nodes.findIndex(item => String(item.id) === id);
\t\t\t\t\t\t\t\tif (index < 0) return new Response(JSON.stringify({ error: '节点不存在或已被删除，请重新打开编辑窗口' }), { status: 404, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t\tif (状态.nodes.some((item, i) => i !== index && 规范化自定义优选行(item.line) === 新行)) {
\t\t\t\t\t\t\t\t\treturn new Response(JSON.stringify({ error: '修改后会与另一条节点完全重复，请调整节点名称' }), { status: 409, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t\t}

\t\t\t\t\t\t\t\tconst 旧行 = 规范化自定义优选行(状态.nodes[index].line);
\t\t\t\t\t\t\t\t状态.nodes[index] = { ...状态.nodes[index], id, line: 新行, proxyip: ProxyIP };
\t\t\t\t\t\t\t\tconst 当前文本 = await env.KV.get('ADD.txt') || '';
\t\t\t\t\t\t\t\tconst 当前行列表 = 当前文本.split(/\\r?\\n/).map(规范化自定义优选行).filter(Boolean);
\t\t\t\t\t\t\t\tlet 已替换 = false;
\t\t\t\t\t\t\t\tconst 新行列表 = 当前行列表.map(line => {
\t\t\t\t\t\t\t\t\tif (!已替换 && line === 旧行) { 已替换 = true; return 新行; }
\t\t\t\t\t\t\t\t\treturn line;
\t\t\t\t\t\t\t\t});
\t\t\t\t\t\t\t\tif (!已替换) 新行列表.push(新行);

\t\t\t\t\t\t\t\tconst 更新时间 = Date.now();
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
\t\t\t\t\t\t} else if (访问路径 === 'admin/config.json') { // 保存config.json配置"""
s = s.replace(anchor, update_route, 1)

# 4) Popup HTML adds an existing-node selector and dynamic labels.
replace_once(
    '<h2 class="api-optimize-modal-title">添加 ProxyIP 节点</h2>',
    '<h2 class="api-optimize-modal-title" id="proxyIpModalTitle">ProxyIP 节点</h2>',
    'popup title',
)
replace_once(
    "\t\t<div class=\"api-form-group chain-proxy-form\">\n\t\t\t<div class=\"api-form-row-item\">\n\t\t\t\t<label for=\"proxyIpNodeName\">节点名称:</label>",
    "\t\t<div class=\"api-form-group chain-proxy-form\">\n\t\t\t<div class=\"api-form-row-item\">\n\t\t\t\t<label for=\"proxyIpExistingNode\">已有节点:</label>\n\t\t\t\t<select id=\"proxyIpExistingNode\" title=\"选择已有 ProxyIP 节点\" onchange=\"selectProxyIpNode(this.value)\">\n\t\t\t\t\t<option value=\"\">＋ 新增 ProxyIP 节点</option>\n\t\t\t\t</select>\n\t\t\t</div>\n\t\t\t<div class=\"api-form-row-item\">\n\t\t\t\t<label for=\"proxyIpNodeName\">节点名称:</label>",
    'popup selector insertion',
)
replace_once(
    '<p class="proxyip-save-hint">填写节点信息后可直接添加。点击“可用性验证”会在新选项卡调用独立 VPS 上的 ProxyIP Scanner，并自动带入当前 ProxyIP；检测结果不影响添加。添加后点击原页面“保存”才正式生效。</p>',
    '<p class="proxyip-save-hint" id="proxyIpSaveHint">新增节点填写后点击“添加”，再点击原页面“保存”生效；编辑已有节点时点击“保存修改”会按内部节点 ID 直接保存，不需要删除重建。</p>',
    'popup hint',
)
replace_once(
    '#proxyIpNodeModal .proxyip-address-wrap input{flex:1;min-width:0}',
    '#proxyIpNodeModal .proxyip-address-wrap input{flex:1;min-width:0}\n#proxyIpNodeModal select{width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px;background:var(--input-bg,#fff);color:inherit}',
    'popup select CSS',
)

# 5) Frontend keeps the V2 node list and current edit ID.
replace_once(
    "\tconst nativeFetch = window.fetch.bind(window);\n\tlet persistedReady = Promise.resolve();",
    "\tconst nativeFetch = window.fetch.bind(window);\n\tlet persistedReady = Promise.resolve();\n\tlet persistedNodes = [];\n\tlet editingNodeId = '';",
    'frontend state',
)

replace_once(
    "\tfunction cleanLines(value){\n\t\treturn String(value || '').split(/\\r?\\n/).map(canonicalLine).filter(Boolean);\n\t}\n\tfunction normalizeHost(value){",
    """\tfunction cleanLines(value){
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
\tfunction normalizeHost(value){""",
    'frontend editor helpers',
)

replace_once(
    "\t\t\tconst d = await r.json();\n\t\t\tfor (const k of Object.keys(persisted)) delete persisted[k];\n\t\t\tfor (const item of (Array.isArray(d.nodes) ? d.nodes : [])) {\n\t\t\t\tif (item && item.line && item.proxyip) persisted[canonicalLine(item.line)] = String(item.proxyip).trim();\n\t\t\t}\n\t\t} catch (_) {}",
    "\t\t\tconst d = await r.json();\n\t\t\tpersistedNodes = Array.isArray(d.nodes) ? d.nodes.map(item => ({ id: String(item?.id || ''), line: canonicalLine(item?.line), proxyip: String(item?.proxyip || '').trim() })).filter(item => item.line) : [];\n\t\t\tfor (const k of Object.keys(persisted)) delete persisted[k];\n\t\t\tfor (const item of persistedNodes) {\n\t\t\t\tif (item.line && item.proxyip) persisted[item.line] = item.proxyip;\n\t\t\t}\n\t\t\trenderExistingNodeOptions();\n\t\t} catch (_) {}",
    'loadPersisted body',
)

# Replace popup opener by marker range.
start = s.index("\twindow.openProxyIpModal = function(){")
end = s.index("\twindow.closeProxyIpModal = function()", start)
s = s[:start] + """\twindow.openProxyIpModal = async function(){
\t\tconst modal = document.getElementById('proxyIpNodeModal');
\t\tif (!modal) return;
\t\ttry { await persistedReady; await loadPersisted(); } catch (_) {}
\t\tsetEditorMode(null);
\t\tmodal.classList.add('show');
\t\tsetTimeout(function(){ document.getElementById('proxyIpExistingNode')?.focus(); }, 0);
\t};
""" + s[end:]

# Replace add action with add/edit dual mode.
start = s.index("\twindow.addProxyIpNode = function(){")
end = s.index("\n\n\tconst chainBtn = document.getElementById('chainProxyBtn');", start)
s = s[:start] + """\twindow.addProxyIpNode = async function(){
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

\t\t\tif (editingNodeId) {
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

\t\t\tconst lines = cleanLines(textarea.value);
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
\t};""" + s[end:]

required = [
    "访问路径 === 'admin/proxyip-nodes/update'",
    'id="proxyIpExistingNode"',
    "let editingNodeId = '';",
    "button.textContent = '保存修改'",
    "await nativeFetch('/admin/proxyip-nodes/update'",
    'const nodes = 状态.nodes.map(item => ({ id: item.id',
    '首次 V2 迁移持久化失败',
]
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit('post-patch assertions failed: ' + repr(missing))
if s == original:
    raise SystemExit('no changes produced')

path.write_text(s, encoding='utf-8')
