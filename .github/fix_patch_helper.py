from pathlib import Path

p = Path('.github/patch_proxyip_verify.py')
s = p.read_text(encoding='utf-8')
helper_fix = r"helper = helper.replace('\\\\', '\\').replace('\\t', '\t')"
verify_fix = r"verify_js = verify_js.replace('\\\\', '\\').replace('\\t', '\t')"
s = s.replace("if helper_anchor not in s:\n", helper_fix + "\nif helper_anchor not in s:\n", 1)
s = s.replace("if normalize_anchor not in s:\n", verify_fix + "\nif normalize_anchor not in s:\n", 1)
p.write_text(s, encoding='utf-8')
