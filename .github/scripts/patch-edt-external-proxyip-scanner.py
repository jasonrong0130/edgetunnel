from pathlib import Path
import re

worker = Path('_worker.js')
text = worker.read_text(encoding='utf-8')

text = text.replace("import ProxyIPCheckerWorker from './proxyip-checker-source.js';\n", '', 1)

start = "const 内嵌ProxyIP检测器前缀 = '/admin/proxyip-checker';"
end = "async function 注入ProxyIP后台入口(response) {"
if start not in text or end not in text:
    raise SystemExit('ProxyIP checker integration block not found')

replacement = r'''const 内嵌ProxyIP检测器前缀 = '/admin/proxyip-checker';

function 获取外部ProxyIP扫描器配置(env) {
	const baseUrl = String(env.PROXYIP_SCANNER_URL || '').trim().replace(/\/+$/, '');
	const token = String(env.PROXYIP_SCANNER_TOKEN || '').trim();
	const sni = String(env.PROXYIP_SCANNER_SNI || '').trim();
	return { baseUrl, token, sni };
}

function 外部ProxyIP扫描器页面(proxyip = '', defaultSni = '', configured = false) {
	const safeProxy = JSON.stringify(String(proxyip || ''));
	const safeSni = JSON.stringify(String(defaultSni || ''));
	const configuredText = configured ? 'Scanner 已配置' : 'Scanner 尚未配置';
	return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProxyIP 可用性验证</title>
<style>
:root{color-scheme:light dark;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;background:#f5f7fb;color:#111827}.wrap{max-width:900px;margin:48px auto;padding:0 20px}.card{background:#fff;border:1px solid #e5e7eb;border-radius:18px;box-shadow:0 16px 45px rgba(15,23,42,.08);padding:28px}.head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:22px}h1{font-size:24px;margin:0 0 8px}.sub{color:#6b7280;font-size:14px;line-height:1.6}.badge{font-size:12px;padding:6px 10px;border-radius:999px;background:#eef2ff;color:#4338ca;white-space:nowrap}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.field{display:flex;flex-direction:column;gap:7px}.field.full{grid-column:1/-1}label{font-size:13px;font-weight:650}input{width:100%;padding:11px 12px;border:1px solid #d1d5db;border-radius:10px;background:#fff;color:#111827;font-size:14px;outline:none}input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.12)}button{border:0;border-radius:10px;padding:11px 18px;font-weight:700;cursor:pointer}.primary{background:#111827;color:#fff}.primary:disabled{opacity:.55;cursor:not-allowed}.actions{display:flex;gap:10px;margin-top:18px}.result{margin-top:22px;border-top:1px solid #e5e7eb;padding-top:20px;display:none}.summary{font-size:18px;font-weight:800;margin-bottom:14px}.ok{color:#059669}.bad{color:#dc2626}.warn{color:#d97706}.facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.fact{background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:12px}.fact b{display:block;font-size:12px;color:#6b7280;margin-bottom:5px}.fact span{font-size:14px;word-break:break-all}.error{margin-top:12px;padding:12px;border-radius:10px;background:#fef2f2;color:#991b1b;white-space:pre-wrap;font-size:13px}.hint{margin-top:18px;color:#6b7280;font-size:13px;line-height:1.65}@media(max-width:680px){.grid,.facts{grid-template-columns:1fr}.field.full{grid-column:auto}.head{flex-direction:column}}@media(prefers-color-scheme:dark){body{background:#0b1020;color:#e5e7eb}.card{background:#111827;border-color:#263244}.sub,.hint{color:#94a3b8}.badge{background:#312e81;color:#c7d2fe}input{background:#0f172a;color:#e5e7eb;border-color:#334155}.result{border-color:#263244}.fact{background:#0f172a;border-color:#263244}.fact b{color:#94a3b8}}
</style>
</head>
<body><div class="wrap"><div class="card">
<div class="head"><div><h1>ProxyIP 可用性验证</h1><div class="sub">由独立 VPS 上的 ProxyIP Scanner 发起真实 TCP → TLS/SNI → HTTP 验证，不再使用 Cloudflare Worker Socket 探针。</div></div><span class="badge">${configuredText}</span></div>
<div class="grid">
<div class="field full"><label for="proxyip">ProxyIP</label><input id="proxyip" placeholder="IP / 域名:端口"></div>
<div class="field full"><label for="sni">检测 SNI（可选）</label><input id="sni" placeholder="留空则使用 Scanner 服务器默认 SNI"></div>
</div>
<div class="actions"><button class="primary" id="checkBtn">开始验证</button></div>
<div class="hint">这里没有固定的 ipv4/ipv6 检测网站。SNI 可以按实际需要动态指定；留空时由 Scanner 的服务器配置决定检测目标。验证不会影响节点添加或保存。</div>
<div class="result" id="result"><div class="summary" id="summary"></div><div class="facts" id="facts"></div><div class="error" id="error" style="display:none"></div></div>
</div></div>
<script>
const initialProxy=${safeProxy}; const initialSni=${safeSni};
const proxyInput=document.getElementById('proxyip'); const sniInput=document.getElementById('sni');
proxyInput.value=initialProxy; sniInput.value=initialSni;
const btn=document.getElementById('checkBtn'), result=document.getElementById('result'), summary=document.getElementById('summary'), facts=document.getElementById('facts'), errorBox=document.getElementById('error');
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function fact(k,v){return '<div class="fact"><b>'+esc(k)+'</b><span>'+esc(v??'-')+'</span></div>'}
async function run(){
 const proxyip=proxyInput.value.trim(), sni=sniInput.value.trim(); if(!proxyip){proxyInput.focus();return}
 btn.disabled=true; btn.textContent='验证中…'; result.style.display='block'; summary.className='summary warn'; summary.textContent='正在由外部 VPS 验证…'; facts.innerHTML=''; errorBox.style.display='none';
 try{
  const r=await fetch('/admin/proxyip-checker/check',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({proxyip,sni})});
  let d; try{d=await r.json()}catch(_){d={error:'Scanner 返回了非 JSON 响应'}}
  if(!r.ok) throw new Error(d.detail||d.error||('HTTP '+r.status));
  const ok=!!d.available; summary.className='summary '+(ok?'ok':'bad'); summary.textContent=ok?'✅ 可用':'❌ 不可用';
  facts.innerHTML=[fact('ProxyIP',d.proxyip||proxyip),fact('SNI',d.sni||sni||'Scanner 默认'),fact('TCP',d.tcp_ms==null?'-':d.tcp_ms+' ms'),fact('TLS',d.tls_ms==null?'-':d.tls_ms+' ms'),fact('HTTP',d.http_status),fact('Cloudflare',d.cloudflare_reached?'已确认':'未确认'),fact('出口 IP',d.exit_ip),fact('国家/地区',d.country),fact('Colo',d.colo),fact('入口=出口',d.exit_match),fact('验证方式',d.validation_mode),fact('错误阶段',d.error_stage)].join('');
  if(d.error){errorBox.style.display='block';errorBox.textContent=d.error}
 }catch(e){summary.className='summary warn'; summary.textContent='⚠️ 无法完成验证'; errorBox.style.display='block'; errorBox.textContent=e.message||String(e)}
 finally{btn.disabled=false;btn.textContent='开始验证'}
}
btn.addEventListener('click',run); proxyInput.addEventListener('keydown',e=>{if(e.key==='Enter')run()});
if(initialProxy) setTimeout(run,80);
</script></body></html>`;
}

async function 调用外部ProxyIP扫描器(request, env, input = {}) {
	const { baseUrl, token, sni: defaultSni } = 获取外部ProxyIP扫描器配置(env);
	if (!baseUrl || !token) {
		return Response.json({ available: false, error_stage: 'config', error: 'PROXYIP_SCANNER_URL 或 PROXYIP_SCANNER_TOKEN 未配置' }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
	}
	let scannerUrl;
	try { scannerUrl = new URL(baseUrl) }
	catch (_) { return Response.json({ available: false, error_stage: 'config', error: 'PROXYIP_SCANNER_URL 格式无效' }, { status: 503 }); }
	if (scannerUrl.protocol !== 'https:' && scannerUrl.hostname !== '127.0.0.1' && scannerUrl.hostname !== 'localhost') {
		return Response.json({ available: false, error_stage: 'config', error: 'ProxyIP Scanner 公网地址必须使用 HTTPS' }, { status: 503 });
	}
	const proxyip = String(input.proxyip || '').trim().replace(/^proxyip:\/\//i, '');
	if (!proxyip) return Response.json({ available: false, error_stage: 'input', error: 'proxyip is required' }, { status: 400 });
	const payload = { proxyip, expect_cloudflare: input.expect_cloudflare !== false };
	const requestedSni = String(input.sni || defaultSni || '').trim();
	if (requestedSni) payload.sni = requestedSni;
	if (input.path) payload.path = String(input.path);
	if (input.generic_sni) payload.generic_sni = String(input.generic_sni);
	if (input.timeout) payload.timeout = Number(input.timeout);
	try {
		const upstream = await fetch(new URL('/api/integrations/edt/check', scannerUrl).toString(), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
			body: JSON.stringify(payload),
		});
		const body = await upstream.text();
		const headers = new Headers({ 'Content-Type': upstream.headers.get('content-type') || 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
		return new Response(body, { status: upstream.status, headers });
	} catch (error) {
		return Response.json({ available: false, error_stage: 'scanner', error: `ProxyIP Scanner 请求失败: ${error?.message || error}` }, { status: 502, headers: { 'Cache-Control': 'no-store' } });
	}
}

async function 处理内嵌ProxyIP检测器(request, env) {
	const outerUrl = new URL(request.url);
	let suffix = outerUrl.pathname.slice(内嵌ProxyIP检测器前缀.length);
	if (!suffix) suffix = '/';
	else if (!suffix.startsWith('/')) suffix = '/' + suffix;

	if (suffix === '/check') {
		let input = {};
		if (request.method === 'POST') {
			try { input = await request.json(); }
			catch (_) { return Response.json({ available: false, error_stage: 'input', error: '请求 JSON 无效' }, { status: 400 }); }
		} else {
			input = { proxyip: outerUrl.searchParams.get('proxyip') || '', sni: outerUrl.searchParams.get('sni') || '' };
		}
		return await 调用外部ProxyIP扫描器(request, env, input);
	}

	let proxyip = '';
	if (suffix !== '/') {
		try { proxyip = decodeURIComponent(suffix.slice(1)); }
		catch (_) { proxyip = suffix.slice(1); }
	}
	const cfg = 获取外部ProxyIP扫描器配置(env);
	return new Response(外部ProxyIP扫描器页面(proxyip, cfg.sni, Boolean(cfg.baseUrl && cfg.token)), {
		status: 200,
		headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY' },
	});
}

'''

before, after = text.split(start, 1)
_, tail = after.split(end, 1)
text = before + replacement + end + tail

text = text.replace(
    '点击“可用性验证”会在新选项卡打开内置 ProxyIP 检测中心，并自动带入当前 ProxyIP；检测结果不影响添加。',
    '点击“可用性验证”会在新选项卡调用独立 VPS 上的 ProxyIP Scanner，并自动带入当前 ProxyIP；检测结果不影响添加。'
)
text = text.replace('// 内嵌 ProxyIP 检测中心', '// 外部 VPS ProxyIP Scanner 验证入口')

worker.write_text(text, encoding='utf-8')

for obsolete in [
    Path('proxyip-checker-source.js'),
    Path('THIRD_PARTY_LICENSES/CF-Workers-CheckProxyIP-LICENSE'),
]:
    if obsolete.exists():
        obsolete.unlink()

checks = {
    'old import still present': "ProxyIPCheckerWorker" in text,
    'old fixed probe still present': "090227.xyz" in text,
    'scanner endpoint missing': "/api/integrations/edt/check" not in text,
    'scanner env missing': "PROXYIP_SCANNER_URL" not in text or "PROXYIP_SCANNER_TOKEN" not in text,
}
failed = [name for name, bad in checks.items() if bad]
if failed:
    raise SystemExit('; '.join(failed))
