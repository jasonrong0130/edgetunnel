from pathlib import Path

# One-shot patch helper for candidate/force-proxyip.
p = Path('_worker.js')
s = p.read_text(encoding='utf-8-sig')
old = "\t\t\tif (!body.includes(chainButtonMarker)) throw new Error('未找到原版链式代理按钮');"
new = "\t\t\t// 静态标记未命中时继续执行；后续 ensureButton() 会按 chainProxyBtn 动态插入 PROXYIP 按钮。"
if old not in s:
    raise SystemExit('target throw line not found or already patched')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
