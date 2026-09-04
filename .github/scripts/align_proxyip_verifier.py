from pathlib import Path

p = Path('_worker.js')
s = p.read_text(encoding='utf-8-sig')

s = s.replace("import { connect as 官方TCP连接 } from 'cloudflare:sockets';\n", '', 1)

start = s.find('async function 检测ProxyIP可用性(request, proxyValue) {')
end = s.find('async function 注入ProxyIP后台入口(response) {')
if start == -1 or end == -1 or end <= start:
    raise SystemExit('ProxyIP verifier helper block not found')
s = s[:start] + s[end:]

old_route = """\t\t} else if (管理员密码 && upgradeHeader === 'websocket' && 访问路径 === 'admin/proxyip-check-ws') {// ProxyIP 可用性验证：使用与正式节点一致的 WebSocket 请求上下文
\t\t\tconst cookies = request.headers.get('Cookie') || '';
\t\t\tconst authCookie = cookies.split(';').find(c => c.trim().startsWith('auth='))?.split('=')[1];
\t\t\tif (!authCookie || authCookie !== await MD5MD5(UA + 加密秘钥 + 管理员密码)) return new Response('Unauthorized', { status: 403 });
\t\t\tconst proxyValue = url.searchParams.get('proxyip');
\t\t\tif (!proxyValue) return new Response('Missing proxyip', { status: 400 });
\t\t\treturn await 处理ProxyIP验证WS(request, proxyValue);
\t\t} else if (管理员密码 && upgradeHeader === 'websocket') {// WebSocket代理"""
new_route = """\t\t} else if (管理员密码 && upgradeHeader === 'websocket') {// WebSocket代理"""
if old_route not in s:
    raise SystemExit('ProxyIP WS route block not found')
s = s.replace(old_route, new_route, 1)

old_admin_check = """\t\t\t\t\t} else if (访问路径 === 'admin/check') {// 代理检查
\t\t\t\t\t\tif (url.searchParams.has('proxyip')) {
\t\t\t\t\t\t\ttry {
\t\t\t\t\t\t\t\tconst result = await 检测ProxyIP可用性(request, url.searchParams.get('proxyip'));
\t\t\t\t\t\t\t\treturn new Response(JSON.stringify(result, null, 2), { status: 200, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t} catch (err) {
\t\t\t\t\t\t\t\treturn new Response(JSON.stringify({ success: false, msg: 'ProxyIP链路验证失败：' + (err?.message || err), error: err?.message || String(err) }, null, 2), { status: 502, headers: { 'Content-Type': 'application/json;charset=utf-8' } });
\t\t\t\t\t\t\t}
\t\t\t\t\t\t}
\t\t\t\t\t\tconst 代理协议"""
new_admin_check = """\t\t\t\t\t} else if (访问路径 === 'admin/check') {// 代理检查
\t\t\t\t\t\tconst 代理协议"""
if old_admin_check not in s:
    raise SystemExit('admin/check ProxyIP branch not found')
s = s.replace(old_admin_check, new_admin_check, 1)

verify_start = s.find('\twindow.verifyProxyIpAvailability = async function(){')
verify_end = s.find('\tfunction ensureButton(){', verify_start)
if verify_start == -1 or verify_end == -1:
    raise SystemExit('client ProxyIP verifier block not found')

new_verify = """\twindow.verifyProxyIpAvailability = async function(){
\t\tconst verifyBtn = document.getElementById('btnVerifyProxyIp');
\t\tconst addBtn = document.getElementById('btnAddProxyIp');
\t\tlet key = '';
\t\ttry {
\t\t\tkey = getProxyIpValidationKey();
\t\t\tconst rawProxy = normalizeProxy(document.getElementById('proxyIpAddress')?.value);
\t\t\tlet checkerProxy = rawProxy;
\t\t\ttry {
\t\t\t\tconst parsed = new URL('https://' + rawProxy);
\t\t\t\tcheckerProxy = String(parsed.hostname || rawProxy).replace(/^\\[|\\]$/g, '');
\t\t\t} catch (_) {}
\t\t\tproxyIpChecking = true;
\t\t\tproxyIpValidatedKey = '';
\t\t\tif (verifyBtn) { verifyBtn.disabled = true; verifyBtn.textContent = '验证中...'; }
\t\t\tif (addBtn) addBtn.disabled = true;
\t\t\tsetProxyIpStatus('checking', '正在使用原版 ProxyIP 可用性检测服务验证...');
\t\t\tconst controller = new AbortController();
\t\t\tconst timer = setTimeout(() => controller.abort(), 10000);
\t\t\tlet response;
\t\t\ttry {
\t\t\t\tresponse = await nativeFetch('https://api.090227.xyz/check?proxyip=' + encodeURIComponent(checkerProxy), { signal: controller.signal, cache: 'no-store' });
\t\t\t} finally {
\t\t\t\tclearTimeout(timer);
\t\t\t}
\t\t\tlet data = {};
\t\t\ttry { data = await response.json(); } catch (_) {}
\t\t\tif (!response.ok || !data.success) throw new Error(data.msg || data.error || ('HTTP ' + response.status));
\t\t\tif (key !== getProxyIpValidationKey()) throw new Error('参数已变化，请重新验证');
\t\t\tproxyIpValidatedKey = key;
\t\t\tif (addBtn) addBtn.disabled = false;
\t\t\tlet detail = '验证通过';
\t\t\tif (Number.isFinite(Number(data.responseTime))) detail += ' · ' + Number(data.responseTime) + 'ms';
\t\t\tif (data.supports_ipv4 === true) detail += ' · IPv4';
\t\t\tif (data.supports_ipv6 === true) detail += ' · IPv6';
\t\t\tsetProxyIpStatus('success', detail);
\t\t} catch (error) {
\t\t\tproxyIpValidatedKey = '';
\t\t\tif (addBtn) addBtn.disabled = true;
\t\t\tconst message = error?.name === 'AbortError' ? '原版 ProxyIP 检测服务超时' : (error?.message || String(error));
\t\t\tsetProxyIpStatus('error', '验证失败：' + message);
\t\t} finally {
\t\t\tproxyIpChecking = false;
\t\t\tif (verifyBtn) verifyBtn.textContent = '可用性验证';
\t\t\tupdateProxyIpVerifyButton();
\t\t}
\t};
"""
s = s[:verify_start] + new_verify + s[verify_end:]

s = s.replace(
    '先验证 ProxyIP 链路；验证通过后才可添加。添加后只会进入“自定义优选地址”，点击原页面“保存”后才正式生效。',
    '先按原版“获取更多 PROXYIP”的方式验证可用性；验证通过后才可添加。添加后只会进入“自定义优选地址”，点击原页面“保存”后才正式生效。',
    1,
)

p.write_text(s, encoding='utf-8')
