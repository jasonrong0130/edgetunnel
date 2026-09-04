from pathlib import Path

p = Path('.github/apply_proxyip_admin.py')
s = p.read_text(encoding='utf-8')
old = r"    return value.replace('\\t', '\t')" + "\n"
new = r"    return value.replace('\\t', '\t').replace('\\\\', '\\')" + "\n"
if old not in s:
    raise SystemExit('untab helper line not found')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
print('fixed patch helper escaping')
