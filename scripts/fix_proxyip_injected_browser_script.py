from pathlib import Path
import re

path = Path('_worker.js')
s = path.read_text(encoding='utf-8')
original = s

start_marker = '<script data-custom-proxyip-ui="1">\n'
end_marker = '\n</script>`;'
start = s.find(start_marker)
if start < 0:
    raise SystemExit('ProxyIP injected script start marker not found')
end = s.find(end_marker, start)
if end < 0:
    raise SystemExit('ProxyIP injected script end marker not found')

body_start = start + len(start_marker)
body = s[body_start:end]

# Repair accidental literal "\\t" indentation introduced by the prior one-shot patch.
def fix_indent(match):
    token = match.group(1)
    return '\t' * (len(token) // 2)

body = re.sub(r'(?m)^((?:\\t)+)', fix_indent, body)

# Repair over-escaped newline/carriage-return literals inside the browser-side helper.
replacements = {
    "value[i] !== '\\\\n'": "value[i] !== '\\n'",
    "raw.endsWith('\\\\r')": "raw.endsWith('\\r')",
    ".split('\\\\n')": ".split('\\n')",
    "? '\\\\n' : '')": "? '\\n' : '')",
}
for old, new in replacements.items():
    body = body.replace(old, new)

# Hard assertions: these were the production breakages.
if re.search(r'(?m)^\\t', body):
    raise SystemExit('literal \\t indentation still exists in injected browser script')
for bad in ["value[i] !== '\\\\n'", "raw.endsWith('\\\\r')", ".split('\\\\n')"]:
    if bad in body:
        raise SystemExit(f'over-escaped browser literal still exists: {bad!r}')

required = [
    "let persistedNodes = [];",
    "function setupProxyTextareaProtection(){",
    "textarea.addEventListener('beforeinput'",
    "textarea.addEventListener('cut'",
    "textarea.addEventListener('paste'",
    "btn.textContent = 'PROXYIP';",
    "proxyip-locked-line",
]
missing = [x for x in required if x not in body]
if missing:
    raise SystemExit('required injected browser features missing: ' + repr(missing))

s = s[:body_start] + body + s[end:]
if s == original:
    raise SystemExit('no repair changes produced')
path.write_text(s, encoding='utf-8')

# Emit exactly what the browser receives from String.raw so CI can syntax-check it separately.
Path('/tmp/proxyip-injected-browser.js').write_text(body, encoding='utf-8')
