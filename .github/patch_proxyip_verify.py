from pathlib import Path

p = Path('_worker.js')
s = p.read_text(encoding='utf-8-sig')

old_css = "#proxyIpNodeBtn.proxyip-node-btn{background:linear-gradient(135deg,#ef4444 0%,#dc2626 100%)!important;color:#fff!important;box-shadow:0 4px 15px rgba(220,38,38,.40)!important;padding:10px 20px!important;font-size:17px!important;font-weight:600!important;line-height:19px!important;letter-spacing:.5px!important;border-radius:12px!important;box-sizing:border-box!important}"
new_css = "#proxyIpNodeBtn.proxyip-node-btn{background:linear-gradient(135deg,#ef4444 0%,#dc2626 100%)!important;color:#fff!important;box-shadow:0 4px 15px rgba(220,38,38,.40)!important;text-align:center!important}"
if old_css not in s:
    raise SystemExit('button CSS anchor not found')
s = s.replace(old_css, new_css, 1)

old_sync = """\tfunction syncButton(){
\t\tconst source = document.getElementById('chainProxyBtn');
\t\tconst btn = ensureButton();
\t\tif (!source || !btn) return;
\t\tbtn.classList.toggle('hidden-section', source.classList.contains('hidden-section'));
\t\tbtn.style.display = source.style.display || '';
\t\trequestAnimationFrame(function(){
\t\t\tconst rect = source.getBoundingClientRect();
\t\t\tif (rect.width > 0) btn.style.setProperty('width', rect.width + 'px', 'important');
\t\t\tif (rect.height > 0) btn.style.setProperty('height', rect.height + 'px', 'important');
\t\t});
\t}
"""
new_sync = """\tfunction syncButton(){
\t\tconst source = document.getElementById('chainProxyBtn');
\t\tconst btn = ensureButton();
\t\tif (!source || !btn) return;
\t\tbtn.classList.toggle('hidden-section', source.classList.contains('hidden-section'));
\t\tbtn.style.display = source.style.display || '';
\t}
"""
if old_sync not in s:
    raise SystemExit('syncButton anchor not found')
s = s.replace(old_sync, new_sync, 1)

old_observer = "\tif (chainBtn) { new MutationObserver(syncButton).observe(chainBtn, { attributes: true, attributeFilter: ['class','style'] }); if (typeof ResizeObserver !== 'undefined') new ResizeObserver(syncButton).observe(chainBtn); }"
new_observer = "\tif (chainBtn) new MutationObserver(syncButton).observe(chainBtn, { attributes: true, attributeFilter: ['class','style'] });"
if old_observer not in s:
    raise SystemExit('observer anchor not found')
s = s.replace(old_observer, new_observer, 1)

helper_anchor = "async function 注入ProxyIP后台入口(response) {"
helper = r"""async function 检测ProxyIP可用性(request, proxyValue) {
\tconst endpoint = 规范化ProxyIP端点(proxyValue);
\tconst parsed = new URL('https://' + endpoint);
\tconst hostname = stripIPv6Brackets(parsed.hostname);
\tconst port = Number(parsed.port || 443);
\tconst startTime = Date.now();
\tconst TCP连接 = 创建请求TCP连接器(request);
\tlet tcpSocket = null, tlsSocket = null;
\tconst withTimeout = (promise, ms, message) => Promise.race([
\t\tpromise,
\t\tnew Promise((_, reject) => setTimeout(() => reject(new Error(message)), ms))
\t]);
\ttry {
\t\ttcpSocket = TCP连接({ hostname, port });
\t\tif (tcpSocket.opened) await withTimeout(tcpSocket.opened, 5000, 'ProxyIP TCP连接超时');
\t\ttlsSocket = new TlsClient(tcpSocket, { serverName: 'cloudflare.com', insecure: true });
\t\tawait withTimeout(tlsSocket.handshake(), 6000, 'ProxyIP TLS握手超时');
\t\tconst encoder = new TextEncoder(), decoder = new TextDecoder();
\t\tawait withTimeout(tlsSocket.write(encoder.encode('GET /cdn-cgi/trace HTTP/1.1\\r\\nHost: cloudflare.com\\r\\nUser-Agent: Mozilla/5.0\\r\\nConnection: close\\r\\n\\r\\n')), 5000, 'ProxyIP检测请求写入超时');
\t\tlet responseBuffer = new Uint8Array(0);
\t\tconst deadline = Date.now() + 8000, maxBytes = 64 * 1024;
\t\twhile (Date.now() < deadline && responseBuffer.length < maxBytes) {
\t\t\tconst remain = Math.max(1, deadline - Date.now());
\t\t\tconst value = await withTimeout(tlsSocket.read(), remain, 'ProxyIP检测响应超时');
\t\t\tif (!value) break;
\t\t\tif (value.byteLength === 0) continue;
\t\t\tconst merged = new Uint8Array(responseBuffer.length + value.byteLength);
\t\t\tmerged.set(responseBuffer, 0);
\t\t\tmerged.set(value, responseBuffer.length);
\t\t\tresponseBuffer = merged;
\t\t\tconst partial = decoder.decode(responseBuffer);
\t\t\tif (/(?:^|\\n)ip=.+/m.test(partial) && /(?:^|\\n)loc=.+/m.test(partial)) break;
\t\t}
\t\tif (!responseBuffer.length) throw new Error('ProxyIP未返回检测数据');
\t\tconst responseText = decoder.decode(responseBuffer);
\t\tconst statusLine = responseText.split('\\r\\n')[0] || '';
\t\tconst statusMatch = statusLine.match(/HTTP\\/\\d\\.\\d\\s+(\\d+)/);
\t\tconst statusCode = statusMatch ? Number(statusMatch[1]) : NaN;
\t\tif (!Number.isFinite(statusCode) || statusCode < 200 || statusCode >= 300) throw new Error('ProxyIP检测请求失败: ' + (statusLine || '无效响应'));
\t\tconst ip = responseText.match(/(?:^|\\n)ip=([^\\r\\n]+)/m)?.[1]?.trim();
\t\tconst loc = responseText.match(/(?:^|\\n)loc=([^\\r\\n]+)/m)?.[1]?.trim() || '';
\t\tconst colo = responseText.match(/(?:^|\\n)colo=([^\\r\\n]+)/m)?.[1]?.trim() || '';
\t\tif (!ip) throw new Error('ProxyIP检测响应中未找到出口IP');
\t\treturn { success: true, proxyip: endpoint, ip, loc, colo, latency: Date.now() - startTime };
\t} finally {
\t\ttry { tlsSocket?.close?.(); } catch (_) {}
\t\ttry { tcpSocket?.close?.(); } catch (_) {}
\t}
}

"""
if helper_anchor not in s:
    raise SystemExit('helper insert anchor not found')
s = s.replace(helper_anchor, helper + helper_anchor, 1)

check_anchor = "\t\t\t\t\t} else if (访问路径 === 'admin/check') {// 代理检查\n\t\t\t\t\t\tconst 代理协议 = ['socks5', 'http', 'https', 'turn', 'sstp'].find(类型 => url.searchParams.has(类型)) || null;"
check_repl = "\t\t\t\t\t} else if (访问路径 === 'admin/check') {// 代理检查\n\t\t\t\t\t\tif (url.searchParams.has('proxyip')) {\n\t\t\t\t\t\t\ttry {\n\t\t\t\t\t\t\t\tconst result = await 检测ProxyIP可用性(request, url.searchParams.get('proxyip'));\n\t\t\t\t\t\t\t\treturn new Response(JSON.stringify(result, null, 2), { status: 200, headers: { 'Content-Type': 'application/json;charset=utf-8' } });\n\t\t\t\t\t\t\t} catch (err) {\n\t\t\t\t\t\t\t\treturn new Response(JSON.stringify({ success: false, msg: 'ProxyIP链路验证失败：' + (err?.message || err), error: err?.message || String(err) }, null, 2), { status: 502, headers: { 'Content-Type': 'application/json;charset=utf-8' } });\n\t\t\t\t\t\t\t}\n\t\t\t\t\t\t}\n\t\t\t\t\t\tconst 代理协议 = ['socks5', 'http', 'https', 'turn', 'sstp'].find(类型 => url.searchParams.has(类型)) || null;"
if check_anchor not in s:
    raise SystemExit('admin/check anchor not found')
s = s.replace(check_anchor, check_repl, 1)

status_css_anchor = "#proxyIpNodeModal .proxyip-add-btn{background:linear-gradient(135deg,#ef4444 0%,#dc2626 100%)!important;color:#fff!important}\n"
status_css = status_css_anchor + "#proxyIpNodeStatus{display:none;margin:8px 0 20px;padding:14px 16px;border-radius:8px;color:#fff;font-size:14px;line-height:1.5}\n#proxyIpNodeStatus.checking{display:block;background:linear-gradient(135deg,#3b82f6 0%,#1d4ed8 100%)}\n#proxyIpNodeStatus.success{display:block;background:linear-gradient(135deg,#10b981 0%,#059669 100%)}\n#proxyIpNodeStatus.error{display:block;background:linear-gradient(135deg,#ef4444 0%,#dc2626 100%)}\n"
if status_css_anchor not in s:
    raise SystemExit('status CSS anchor not found')
s = s.replace(status_css_anchor, status_css, 1)

old_buttons = """\t\t<p class=\"proxyip-save-hint\">添加后只会进入“自定义优选地址”；点击原页面“保存”后才会写入并生效。</p>
\t\t<div class=\"api-buttons chain-proxy-buttons\">
\t\t\t<button type=\"button\" class=\"btn btn-chain-add proxyip-add-btn\" onclick=\"addProxyIpNode()\">添加</button>
\t\t\t<button type=\"button\" class=\"btn btn-close-api\" onclick=\"closeProxyIpModal()\">取消</button>
\t\t</div>
"""
new_buttons = """\t\t<p class=\"proxyip-save-hint\">先验证 ProxyIP 链路；验证通过后才可添加。添加后只会进入“自定义优选地址”，点击原页面“保存”后才正式生效。</p>
\t\t<div id=\"proxyIpNodeStatus\"></div>
\t\t<div class=\"api-buttons chain-proxy-buttons\">
\t\t\t<button type=\"button\" class=\"btn btn-verify-api\" id=\"btnVerifyProxyIp\" onclick=\"verifyProxyIpAvailability()\" disabled>可用性验证</button>
\t\t\t<button type=\"button\" class=\"btn btn-chain-add proxyip-add-btn\" id=\"btnAddProxyIp\" onclick=\"addProxyIpNode()\" disabled>添加</button>
\t\t\t<button type=\"button\" class=\"btn btn-close-api\" onclick=\"closeProxyIpModal()\">取消</button>
\t\t</div>
"""
if old_buttons not in s:
    raise SystemExit('modal buttons anchor not found')
s = s.replace(old_buttons, new_buttons, 1)

state_anchor = "\tconst nativeFetch = window.fetch.bind(window);\n"
if state_anchor not in s:
    raise SystemExit('state anchor not found')
s = s.replace(state_anchor, state_anchor + "\tlet proxyIpValidatedKey = '';\n\tlet proxyIpChecking = false;\n", 1)

normalize_anchor = """\tfunction normalizeProxy(value){
\t\tconst v = String(value || '').trim();
\t\tif (!v || v.includes('://') || /[\\s/#$]/.test(v)) throw new Error('ProxyIP 格式无效');
\t\treturn v;
\t}
"""
verify_js = r"""\tfunction getProxyIpValidationKey(){
\t\tconst host = normalizeHost(document.getElementById('proxyIpPreferredHost')?.value);
\t\tconst port = Number(String(document.getElementById('proxyIpPreferredPort')?.value || '443').trim());
\t\tif (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('优选端口必须为 1~65535');
\t\tconst proxyip = normalizeProxy(document.getElementById('proxyIpAddress')?.value);
\t\treturn host + ':' + port + '|' + proxyip;
\t}
\tfunction setProxyIpStatus(type, text){
\t\tconst el = document.getElementById('proxyIpNodeStatus');
\t\tif (!el) return;
\t\tel.className = type || '';
\t\tel.textContent = text || '';
\t\tel.style.display = text ? 'block' : 'none';
\t}
\tfunction updateProxyIpVerifyButton(){
\t\tconst verifyBtn = document.getElementById('btnVerifyProxyIp');
\t\tif (!verifyBtn) return;
\t\tlet valid = false;
\t\ttry { valid = !!getProxyIpValidationKey(); } catch (_) { valid = false; }
\t\tverifyBtn.disabled = proxyIpChecking || !valid;
\t}
\tfunction resetProxyIpValidation(){
\t\tproxyIpValidatedKey = '';
\t\tconst addBtn = document.getElementById('btnAddProxyIp');
\t\tif (addBtn) addBtn.disabled = true;
\t\tif (!proxyIpChecking) setProxyIpStatus('', '');
\t\tupdateProxyIpVerifyButton();
\t}
\twindow.verifyProxyIpAvailability = async function(){
\t\tconst verifyBtn = document.getElementById('btnVerifyProxyIp');
\t\tconst addBtn = document.getElementById('btnAddProxyIp');
\t\tlet key = '';
\t\ttry {
\t\t\tkey = getProxyIpValidationKey();
\t\t\tconst proxyip = normalizeProxy(document.getElementById('proxyIpAddress')?.value);
\t\t\tproxyIpChecking = true;
\t\t\tproxyIpValidatedKey = '';
\t\t\tif (verifyBtn) { verifyBtn.disabled = true; verifyBtn.textContent = '验证中...'; }
\t\t\tif (addBtn) addBtn.disabled = true;
\t\t\tsetProxyIpStatus('checking', '正在验证 Worker → ProxyIP → 目标站点链路...');
\t\t\tconst resp = await nativeFetch('/admin/check?proxyip=' + encodeURIComponent(proxyip) + '&_t=' + Date.now(), { cache: 'no-store' });
\t\t\tlet data = {};
\t\t\ttry { data = await resp.json(); } catch (_) {}
\t\t\tif (!resp.ok || !data.success) throw new Error(data.msg || data.error || ('HTTP ' + resp.status));
\t\t\tif (key !== getProxyIpValidationKey()) throw new Error('参数已变化，请重新验证');
\t\t\tproxyIpValidatedKey = key;
\t\t\tif (addBtn) addBtn.disabled = false;
\t\t\tconst detail = '验证通过：出口 ' + (data.ip || '-') + (data.loc ? ' · ' + data.loc : '') + (data.colo ? ' · ' + data.colo : '') + (Number.isFinite(data.latency) ? ' · ' + data.latency + 'ms' : '');
\t\t\tsetProxyIpStatus('success', detail);
\t\t} catch (error) {
\t\t\tproxyIpValidatedKey = '';
\t\t\tif (addBtn) addBtn.disabled = true;
\t\t\tsetProxyIpStatus('error', '验证失败：' + (error?.message || String(error)));
\t\t} finally {
\t\t\tproxyIpChecking = false;
\t\t\tif (verifyBtn) verifyBtn.textContent = '可用性验证';
\t\t\tupdateProxyIpVerifyButton();
\t\t}
\t};
"""
if normalize_anchor not in s:
    raise SystemExit('normalizeProxy anchor not found')
s = s.replace(normalize_anchor, normalize_anchor + verify_js, 1)

open_anchor = "\t\tmodal.classList.add('show');\n\t\tsetTimeout(function(){ nameInput && nameInput.focus(); }, 0);"
open_repl = "\t\tresetProxyIpValidation();\n\t\tmodal.classList.add('show');\n\t\tsetTimeout(function(){ nameInput && nameInput.focus(); }, 0);"
if open_anchor not in s:
    raise SystemExit('open modal anchor not found')
s = s.replace(open_anchor, open_repl, 1)

add_anchor = "\t\t\tconst proxyip = normalizeProxy(document.getElementById('proxyIpAddress')?.value);\n\t\t\tconst line = host + ':' + port + '#' + name;"
add_repl = "\t\t\tconst proxyip = normalizeProxy(document.getElementById('proxyIpAddress')?.value);\n\t\t\tconst validationKey = host + ':' + port + '|' + proxyip;\n\t\t\tif (!proxyIpValidatedKey || proxyIpValidatedKey !== validationKey) throw new Error('请先完成并通过可用性验证');\n\t\t\tconst line = host + ':' + port + '#' + name;"
if add_anchor not in s:
    raise SystemExit('add validation anchor not found')
s = s.replace(add_anchor, add_repl, 1)

init_anchor = "\tdocument.getElementById('ipMode')?.addEventListener('change', function(){ setTimeout(syncButton, 0); });\n\twindow.addEventListener('resize', syncButton);"
init_repl = "\tdocument.getElementById('ipMode')?.addEventListener('change', function(){ setTimeout(syncButton, 0); });\n\t['proxyIpPreferredHost','proxyIpPreferredPort','proxyIpAddress'].forEach(function(id){ document.getElementById(id)?.addEventListener('input', resetProxyIpValidation); });\n\twindow.addEventListener('resize', syncButton);"
if init_anchor not in s:
    raise SystemExit('init listener anchor not found')
s = s.replace(init_anchor, init_repl, 1)

p.write_text(s, encoding='utf-8')
