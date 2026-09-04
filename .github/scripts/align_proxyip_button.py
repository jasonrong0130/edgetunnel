from pathlib import Path

p = Path('_worker.js')
s = p.read_text(encoding='utf-8-sig')

old = "\t\tlet body = html;\n\n\t\tconst injected = String.raw`"
new = """\t\tlet body = html;
\t\t// 与原版“链式代理”按钮采用同样的静态 DOM 实现：直接放在同一 module-footer 内。
\t\tconst chainButtonMarker = 'onclick=\"openChainProxyModal()\">链式代理</button>';
\t\tif (!body.includes('id=\"proxyIpNodeBtn\"')) {
\t\t\tif (!body.includes(chainButtonMarker)) throw new Error('未找到原版链式代理按钮');
\t\t\tconst proxyButton = '\\n\\t\\t\\t\\t\\t\\t<button type=\"button\" class=\"btn btn-chain-proxy hidden-section proxyip-node-btn\" id=\"proxyIpNodeBtn\" onclick=\"openProxyIpModal()\">ProxyIP节点</button>';
\t\t\tbody = body.replace(chainButtonMarker, chainButtonMarker + proxyButton);
\t\t}

\t\tconst injected = String.raw`"""
if old not in s:
    raise SystemExit('button insertion anchor not found')
s = s.replace(old, new, 1)

old_tail = "\t\tbody = /<\\/body>/i.test(body) ? body.replace(/<\\/body>/i, injected + '</body>') : body + injected;"
new_tail = """\t\tconst bodyCloseIndex = body.toLowerCase().lastIndexOf('</body>');
\t\tbody = bodyCloseIndex >= 0 ? body.slice(0, bodyCloseIndex) + injected + body.slice(bodyCloseIndex) : body + injected;"""
if old_tail not in s:
    raise SystemExit('body injection anchor not found')
s = s.replace(old_tail, new_tail, 1)

p.write_text(s, encoding='utf-8')
