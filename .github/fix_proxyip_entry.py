from pathlib import Path

p = Path('_worker.js')
text = p.read_text(encoding='utf-8-sig')
start_marker = 'async function 注入ProxyIP后台入口(response) {'
end_marker = '\n///////////////////////////////////////////////////////查杀特征码'
start = text.index(start_marker)
end = text.index(end_marker, start)
new_func = '''async function 注入ProxyIP后台入口(response) {
\ttry {
\t\tconst html = await response.text();
\t\tif (html.includes('id="proxyIpNodeBtn"')) {
\t\t\tconst headers = new Headers(response.headers);
\t\t\theaders.delete('content-length'); headers.delete('content-encoding'); headers.set('Cache-Control', 'no-store');
\t\t\treturn new Response(html, { status: response.status, statusText: response.statusText, headers });
\t\t}
\t\tconst proxyButton = '<button type="button" class="btn btn-chain-proxy" id="proxyIpNodeBtn" onclick="location.href=\\'/admin/proxyip\\'">ProxyIP节点</button>';
\t\tconst chainButtonPattern = /(<button\\s+type="button"\\s+class="btn btn-chain-proxy hidden-section"\\s+id="chainProxyBtn"[\\s\\S]*?<\\/button>)/i;
\t\tlet body;
\t\tif (chainButtonPattern.test(html)) {
\t\t\tbody = html.replace(chainButtonPattern, '$1\\n\\t\\t\\t\\t\\t\\t' + proxyButton);
\t\t} else {
\t\t\tconst fallback = '<a id="proxyIpNodeBtn" href="/admin/proxyip" style="position:fixed;right:22px;bottom:22px;z-index:99999;padding:11px 16px;border-radius:12px;background:#f6821f;color:#fff;text-decoration:none;font-weight:600;box-shadow:0 6px 20px rgba(0,0,0,.18)">ProxyIP节点</a>';
\t\t\tbody = /<\\/body>/i.test(html) ? html.replace(/<\\/body>/i, fallback + '</body>') : html + fallback;
\t\t}
\t\tconst headers = new Headers(response.headers);
\t\theaders.delete('content-length'); headers.delete('content-encoding'); headers.set('Cache-Control', 'no-store');
\t\treturn new Response(body, { status: response.status, statusText: response.statusText, headers });
\t} catch (error) {
\t\tlog(`[ProxyIP节点] 后台入口注入失败: ${error?.message || error}`);
\t\treturn response;
\t}
}
'''
text = text[:start] + new_func + text[end:]
p.write_text(text, encoding='utf-8')
print('patched ProxyIP admin entry')
