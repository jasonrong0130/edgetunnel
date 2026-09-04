from pathlib import Path

p = Path('_worker.js')
s = p.read_text(encoding='utf-8-sig')
old = """\tfunction normalizeProxy(value){\n\t\tconst v = String(value || '').trim();\n\t\tif (!v || v.includes('://') || /[\\s/#$]/.test(v)) throw new Error('ProxyIP 格式无效');\n\t\treturn v;\n\t}\n"""
new = """\tfunction normalizeProxy(value){\n\t\tlet v = String(value || '').trim();\n\t\tv = v.replace(/^proxyip:\\/\\//i, '').trim();\n\t\tif (!v || v.includes('://') || /[\\s/#$]/.test(v)) throw new Error('ProxyIP 格式无效');\n\t\treturn v;\n\t}\n"""
if old not in s:
    raise SystemExit('normalizeProxy block not found or already changed')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
