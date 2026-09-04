from pathlib import Path

p = Path('_worker.js')
s = p.read_text(encoding='utf-8-sig')

old_hint = '先按原版“获取更多 PROXYIP”的方式验证可用性；验证通过后才可添加。添加后只会进入“自定义优选地址”，点击原页面“保存”后才正式生效。'
new_hint = '可用性验证为可选项；点击验证会将 ProxyIP 主机提交给原版第三方检测服务，仅作参考，不影响添加。也可以不验证直接添加。添加后只会进入“自定义优选地址”，点击原页面“保存”后才正式生效。'
if old_hint not in s:
    raise SystemExit('hint text not found')
s = s.replace(old_hint, new_hint, 1)

old_update = """\tfunction updateProxyIpVerifyButton(){
\t\tconst verifyBtn = document.getElementById('btnVerifyProxyIp');
\t\tif (!verifyBtn) return;
\t\tlet valid = false;
\t\ttry { valid = !!getProxyIpValidationKey(); } catch (_) { valid = false; }
\t\tverifyBtn.disabled = proxyIpChecking || !valid;
\t}
"""
new_update = """\tfunction updateProxyIpVerifyButton(){
\t\tconst verifyBtn = document.getElementById('btnVerifyProxyIp');
\t\tconst addBtn = document.getElementById('btnAddProxyIp');
\t\tlet valid = false;
\t\ttry {
\t\t\tvalid = !!getProxyIpValidationKey();
\t\t\tconst name = String(document.getElementById('proxyIpNodeName')?.value || '').trim();
\t\t\tvalid = valid && !!name;
\t\t} catch (_) { valid = false; }
\t\tif (verifyBtn) verifyBtn.disabled = proxyIpChecking || !valid;
\t\tif (addBtn) addBtn.disabled = !valid;
\t}
"""
if old_update not in s:
    raise SystemExit('update button function not found')
s = s.replace(old_update, new_update, 1)

old_reset = """\tfunction resetProxyIpValidation(){
\t\tproxyIpValidatedKey = '';
\t\tconst addBtn = document.getElementById('btnAddProxyIp');
\t\tif (addBtn) addBtn.disabled = true;
\t\tif (!proxyIpChecking) setProxyIpStatus('', '');
\t\tupdateProxyIpVerifyButton();
\t}
"""
new_reset = """\tfunction resetProxyIpValidation(){
\t\tproxyIpValidatedKey = '';
\t\tif (!proxyIpChecking) setProxyIpStatus('', '');
\t\tupdateProxyIpVerifyButton();
\t}
"""
if old_reset not in s:
    raise SystemExit('reset validation function not found')
s = s.replace(old_reset, new_reset, 1)

verify_start = s.find('\twindow.verifyProxyIpAvailability = async function(){')
verify_end = s.find('\tfunction ensureButton(){', verify_start)
if verify_start == -1 or verify_end == -1:
    raise SystemExit('verify function block not found')
verify_block = s[verify_start:verify_end]
verify_block = verify_block.replace("\t\tconst addBtn = document.getElementById('btnAddProxyIp');\n", '', 1)
verify_block = verify_block.replace("\t\t\tif (addBtn) addBtn.disabled = true;\n", '')
verify_block = verify_block.replace("\t\t\tif (addBtn) addBtn.disabled = false;\n", '')
old_parse = """\t\t\tlet data = {};
\t\t\ttry { data = await response.json(); } catch (_) {}
\t\t\tif (!response.ok || !data.success) throw new Error(data.msg || data.error || ('HTTP ' + response.status));
"""
new_parse = """\t\t\tconst responseText = await response.text();
\t\t\tlet data = {};
\t\t\ttry { data = JSON.parse(responseText); }
\t\t\tcatch (_) { throw new Error('检测服务返回非 JSON 数据（HTTP ' + response.status + '）'); }
\t\t\tif (!response.ok) throw new Error(data.msg || data.error || ('检测服务请求失败：HTTP ' + response.status));
\t\t\tif (!data.success) throw new Error(data.msg || data.error || '检测服务判定该 ProxyIP 不可用');
"""
if old_parse not in verify_block:
    raise SystemExit('verification response parser not found')
verify_block = verify_block.replace(old_parse, new_parse, 1)
s = s[:verify_start] + verify_block + s[verify_end:]

gate = """\t\t\tconst validationKey = host + ':' + port + '|' + proxyip;
\t\t\tif (!proxyIpValidatedKey || proxyIpValidatedKey !== validationKey) throw new Error('请先完成并通过可用性验证');
"""
if gate not in s:
    raise SystemExit('verification gate not found')
s = s.replace(gate, '', 1)

old_listeners = """\t['proxyIpPreferredHost','proxyIpPreferredPort','proxyIpAddress'].forEach(function(id){ document.getElementById(id)?.addEventListener('input', resetProxyIpValidation); });
"""
new_listeners = """\t['proxyIpPreferredHost','proxyIpPreferredPort','proxyIpAddress'].forEach(function(id){ document.getElementById(id)?.addEventListener('input', resetProxyIpValidation); });
\tdocument.getElementById('proxyIpNodeName')?.addEventListener('input', updateProxyIpVerifyButton);
"""
if old_listeners not in s:
    raise SystemExit('input listeners not found')
s = s.replace(old_listeners, new_listeners, 1)

p.write_text(s, encoding='utf-8')
