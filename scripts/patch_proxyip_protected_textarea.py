from pathlib import Path

path = Path('_worker.js')
s = path.read_text(encoding='utf-8')
original = s

# 1) Visual treatment for protected ProxyIP rows in the custom-IP textarea.
css_anchor = "#proxyIpNodeModal select{width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px;background:var(--input-bg,#fff);color:inherit}"
css_extra = r'''
.proxyip-highlight-wrap{position:relative;width:100%}
.proxyip-highlight-wrap>#customIPs.proxyip-protected-source{position:relative!important;z-index:2;background:transparent!important;color:transparent!important;-webkit-text-fill-color:transparent!important}
.proxyip-highlight-layer{position:absolute;inset:0;z-index:1;pointer-events:none;margin:0;overflow:hidden;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;box-sizing:border-box}
.proxyip-highlight-layer .proxyip-locked-line{color:#dc2626!important;font-weight:700}
.proxyip-protected-hint{margin:6px 0 0;color:#6b7280;font-size:12px;line-height:1.5}
.proxyip-protected-hint b{color:#dc2626}
'''
if css_anchor not in s:
    raise SystemExit('CSS anchor not found')
s = s.replace(css_anchor, css_anchor + css_extra, 1)

# 2) Add protected-textarea state.
state_anchor = "\tlet persistedNodes = [];\n\tlet editingNodeId = '';"
state_replacement = r'''\tlet persistedNodes = [];
\tlet editingNodeId = '';
\tlet proxyHighlightLayer = null;
\tlet proxyHighlightTextarea = null;
\tlet proxyProtectionBound = false;'''
if state_anchor not in s:
    raise SystemExit('state anchor not found')
s = s.replace(state_anchor, state_replacement, 1)

# 3) Add highlighting + whole-line protection helpers before normalizeHost().
helper_anchor = "\tfunction normalizeHost(value){"
helpers = r'''\tfunction getProtectedProxyLineSet(){
\t\tconst set = new Set();
\t\tfor (const item of persistedNodes) {
\t\t\tif (item && item.proxyip) {
\t\t\t\tconst line = canonicalLine(item.line);
\t\t\t\tif (line) set.add(line);
\t\t\t}
\t\t}
\t\tfor (const [line, proxyip] of Object.entries(pending)) {
\t\t\tif (proxyip) {
\t\t\t\tconst key = canonicalLine(line);
\t\t\t\tif (key) set.add(key);
\t\t\t}
\t\t}
\t\treturn set;
\t}
\tfunction proxyLineRanges(text){
\t\tconst value = String(text || '');
\t\tconst protectedSet = getProtectedProxyLineSet();
\t\tconst ranges = [];
\t\tlet start = 0;
\t\tfor (let i = 0; i <= value.length; i++) {
\t\t\tif (i !== value.length && value[i] !== '\\n') continue;
\t\t\tlet raw = value.slice(start, i);
\t\t\tif (raw.endsWith('\\r')) raw = raw.slice(0, -1);
\t\t\tconst key = canonicalLine(raw);
\t\t\tranges.push({ start, end: i, key, protected: !!key && protectedSet.has(key) });
\t\t\tstart = i + 1;
\t\t}
\t\treturn ranges;
\t}
\tfunction proxySelectionTouchesProtected(textarea, affectStart, affectEnd){
\t\treturn proxyLineRanges(textarea.value).filter(r => {
\t\t\tif (!r.protected) return false;
\t\t\tif (affectStart === affectEnd) return affectStart >= r.start && affectStart <= r.end;
\t\t\treturn affectEnd > r.start && affectStart < r.end;
\t\t});
\t}
\tfunction proxySelectionCoversWholeRows(start, end, ranges){
\t\treturn ranges.every(r => start <= r.start && end >= r.end);
\t}
\tfunction proxyLockedMessage(){
\t\tconst msg = '红色 ProxyIP 节点内容已锁定：可复制、整行剪切/删除、粘贴调整顺序；修改 IP、端口、名称或 ProxyIP 请使用 PROXYIP 弹窗。';
\t\tif (typeof showToast === 'function') showToast(msg, 'warning');
\t\telse console.warn(msg);
\t}
\tfunction escapeProxyHighlight(value){
\t\treturn String(value || '').replace(/[&<>]/g, ch => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;' }[ch]));
\t}
\tfunction syncProxyTextareaHighlight(){
\t\tconst textarea = proxyHighlightTextarea || document.getElementById('customIPs');
\t\tconst layer = proxyHighlightLayer;
\t\tif (!textarea || !layer) return;
\t\tconst protectedSet = getProtectedProxyLineSet();
\t\tconst rawLines = String(textarea.value || '').split('\\n');
\t\tlayer.innerHTML = rawLines.map((raw, index) => {
\t\t\tconst display = raw.endsWith('\\r') ? raw.slice(0, -1) : raw;
\t\t\tconst key = canonicalLine(display);
\t\t\tconst cls = key && protectedSet.has(key) ? 'proxyip-locked-line' : '';
\t\t\treturn '<span class="' + cls + '">' + (escapeProxyHighlight(display) || ' ') + '</span>' + (index < rawLines.length - 1 ? '\\n' : '');
\t\t}).join('');
\t\tlayer.scrollTop = textarea.scrollTop;
\t\tlayer.scrollLeft = textarea.scrollLeft;
\t}
\tfunction setupProxyTextareaProtection(){
\t\tconst textarea = document.getElementById('customIPs');
\t\tif (!textarea) return;
\t\tif (proxyHighlightTextarea !== textarea || !proxyHighlightLayer) {
\t\t\tproxyHighlightTextarea = textarea;
\t\t\tlet wrap = textarea.parentElement && textarea.parentElement.classList?.contains('proxyip-highlight-wrap') ? textarea.parentElement : null;
\t\t\tif (!wrap) {
\t\t\t\twrap = document.createElement('div');
\t\t\t\twrap.className = 'proxyip-highlight-wrap';
\t\t\t\ttextarea.parentNode.insertBefore(wrap, textarea);
\t\t\t\twrap.appendChild(textarea);
\t\t\t}
\t\t\tlet layer = wrap.querySelector('.proxyip-highlight-layer');
\t\t\tif (!layer) {
\t\t\t\tlayer = document.createElement('pre');
\t\t\t\tlayer.className = 'proxyip-highlight-layer';
\t\t\t\tlayer.setAttribute('aria-hidden', 'true');
\t\t\t\twrap.insertBefore(layer, textarea);
\t\t\t}
\t\t\tproxyHighlightLayer = layer;
\t\t\tconst cs = getComputedStyle(textarea);
\t\t\tfor (const prop of ['fontFamily','fontSize','fontWeight','fontStyle','lineHeight','letterSpacing','textAlign','textTransform','textIndent','tabSize','paddingTop','paddingRight','paddingBottom','paddingLeft','borderTopWidth','borderRightWidth','borderBottomWidth','borderLeftWidth','borderTopStyle','borderRightStyle','borderBottomStyle','borderLeftStyle','borderRadius','boxSizing']) {
\t\t\t\ttry { layer.style[prop] = cs[prop]; } catch (_) {}
\t\t\t}
\t\t\tlayer.style.borderColor = 'transparent';
\t\t\tlayer.style.backgroundColor = cs.backgroundColor;
\t\t\tlayer.style.color = cs.color;
\t\t\ttextarea.classList.add('proxyip-protected-source');
\t\t\ttextarea.style.setProperty('caret-color', cs.color || '#111827', 'important');
\t\t\tlet hint = wrap.nextElementSibling;
\t\t\tif (!hint || !hint.classList?.contains('proxyip-protected-hint')) {
\t\t\t\thint = document.createElement('div');
\t\t\t\thint.className = 'proxyip-protected-hint';
\t\t\t\thint.innerHTML = '<b>红色</b> = 已绑定 ProxyIP，内容锁定；可复制、整行剪切/删除、粘贴调整顺序，修改请点 PROXYIP。';
\t\t\t\twrap.insertAdjacentElement('afterend', hint);
\t\t\t}
\t\t\ttextarea.addEventListener('scroll', syncProxyTextareaHighlight);
\t\t\ttextarea.addEventListener('input', syncProxyTextareaHighlight);
\t\t}
\t\tif (!proxyProtectionBound) {
\t\t\tproxyProtectionBound = true;
\t\t\ttextarea.addEventListener('beforeinput', function(event){
\t\t\t\tconst type = String(event.inputType || '');
\t\t\t\tif (!type || type.startsWith('history')) return;
\t\t\t\tconst text = textarea.value;
\t\t\t\tconst start = Number(textarea.selectionStart || 0), end = Number(textarea.selectionEnd || start);
\t\t\t\tlet affectStart = start, affectEnd = end;
\t\t\t\tif (start === end && type === 'deleteContentBackward') affectStart = Math.max(0, start - 1);
\t\t\t\tif (start === end && type === 'deleteContentForward') affectEnd = Math.min(text.length, end + 1);
\t\t\t\tconst touched = proxySelectionTouchesProtected(textarea, affectStart, affectEnd);
\t\t\t\tif (!touched.length) return;
\t\t\t\tconst deletion = type === 'deleteByCut' || type === 'deleteByDrag' || type.startsWith('deleteContent');
\t\t\t\tif (deletion && start !== end && proxySelectionCoversWholeRows(start, end, touched)) return;
\t\t\t\tevent.preventDefault();
\t\t\t\tproxyLockedMessage();
\t\t\t});
\t\t\ttextarea.addEventListener('cut', function(event){
\t\t\t\tconst start = Number(textarea.selectionStart || 0), end = Number(textarea.selectionEnd || start);
\t\t\t\tif (start === end) return;
\t\t\t\tconst touched = proxySelectionTouchesProtected(textarea, start, end);
\t\t\t\tif (touched.length && !proxySelectionCoversWholeRows(start, end, touched)) {
\t\t\t\t\tevent.preventDefault();
\t\t\t\t\tproxyLockedMessage();
\t\t\t\t}
\t\t\t});
\t\t\ttextarea.addEventListener('paste', function(event){
\t\t\t\tconst start = Number(textarea.selectionStart || 0), end = Number(textarea.selectionEnd || start);
\t\t\t\tconst touched = proxySelectionTouchesProtected(textarea, start, end);
\t\t\t\tif (touched.length) {
\t\t\t\t\tevent.preventDefault();
\t\t\t\t\tproxyLockedMessage();
\t\t\t\t}
\t\t\t});
\t\t}
\t\tsyncProxyTextareaHighlight();
\t}

'''
if helper_anchor not in s:
    raise SystemExit('normalizeHost anchor not found')
s = s.replace(helper_anchor, helpers + helper_anchor, 1)

# 4) Refresh red highlighting whenever persisted V2 records are reloaded.
load_anchor = "\t\t\trenderExistingNodeOptions();\n\t\t} catch (_) {}\n\t}\n\n\twindow.fetch = async function(input, init){"
load_replacement = "\t\t\trenderExistingNodeOptions();\n\t\t\tsetupProxyTextareaProtection();\n\t\t\tsyncProxyTextareaHighlight();\n\t\t} catch (_) {}\n\t}\n\n\twindow.fetch = async function(input, init){"
if load_anchor not in s:
    raise SystemExit('loadPersisted anchor not found')
s = s.replace(load_anchor, load_replacement, 1)

# 5) New pending ProxyIP rows become red immediately, before the page-level Save.
new_node_anchor = "\t\t\tpending[canonicalLine(line)] = proxyip;\n\t\t\tif (textarea._refreshLineEditor) textarea._refreshLineEditor();"
new_node_replacement = "\t\t\tpending[canonicalLine(line)] = proxyip;\n\t\t\tsetupProxyTextareaProtection();\n\t\t\tsyncProxyTextareaHighlight();\n\t\t\tif (textarea._refreshLineEditor) textarea._refreshLineEditor();"
if new_node_anchor not in s:
    raise SystemExit('new node anchor not found')
s = s.replace(new_node_anchor, new_node_replacement, 1)

# 6) Ensure protection is active as soon as the injected script initializes.
init_anchor = "\twindow.addEventListener('resize', syncButton);\n\tpersistedReady = loadPersisted();\n\tsyncButton();"
init_replacement = "\twindow.addEventListener('resize', syncButton);\n\tsetupProxyTextareaProtection();\n\tpersistedReady = loadPersisted();\n\tsyncButton();\n\tsyncProxyTextareaHighlight();"
if init_anchor not in s:
    raise SystemExit('init anchor not found')
s = s.replace(init_anchor, init_replacement, 1)

required = [
    'proxyip-highlight-layer',
    'function setupProxyTextareaProtection()',
    'function getProtectedProxyLineSet()',
    '红色 ProxyIP 节点内容已锁定',
    "textarea.addEventListener('beforeinput'",
    "textarea.addEventListener('cut'",
    "textarea.addEventListener('paste'",
]
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit('post-patch assertions failed: ' + repr(missing))
if s == original:
    raise SystemExit('no changes produced')

path.write_text(s, encoding='utf-8')
