from pathlib import Path

p = Path('.github/patch_proxyip_verify.py')
s = p.read_text(encoding='utf-8')
s = s.replace("if helper_anchor not in s:\n", "helper = helper.replace('\\\\t', '\\t')\nif helper_anchor not in s:\n", 1)
s = s.replace("if normalize_anchor not in s:\n", "verify_js = verify_js.replace('\\\\t', '\\t')\nif normalize_anchor not in s:\n", 1)
p.write_text(s, encoding='utf-8')
