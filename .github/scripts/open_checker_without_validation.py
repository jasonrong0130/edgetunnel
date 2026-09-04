from pathlib import Path

p = Path('_worker.js')
s = p.read_text(encoding='utf-8-sig')
old = """\twindow.openProxyIpChecker = function(){\n\t\ttry {\n\t\t\tconst proxyip = normalizeProxy(document.getElementById('proxyIpAddress')?.value);\n\t\t\tconst checkerUrl = '/admin/proxyip-checker/' + encodeURIComponent(proxyip);\n\t\t\tconst tab = window.open('about:blank', '_blank');\n\t\t\tif (!tab) throw new Error('浏览器阻止了新选项卡，请允许本站打开新选项卡');\n\t\t\ttry { tab.opener = null; } catch (_) {}\n\t\t\ttab.location.href = checkerUrl;\n\t\t} catch (error) {\n\t\t\tif (typeof showToast === 'function') showToast(error.message || String(error), 'error');\n\t\t\telse alert(error.message || String(error));\n\t\t}\n\t};\n"""
new = """\twindow.openProxyIpChecker = function(){\n\t\tconst tab = window.open('about:blank', '_blank');\n\t\tif (!tab) {\n\t\t\tconst message = '浏览器阻止了新选项卡，请允许本站打开新选项卡';\n\t\t\tif (typeof showToast === 'function') showToast(message, 'error');\n\t\t\telse alert(message);\n\t\t\treturn;\n\t\t}\n\t\ttry { tab.opener = null; } catch (_) {}\n\t\tlet proxyip = String(document.getElementById('proxyIpAddress')?.value || '').trim();\n\t\tproxyip = proxyip.replace(/^proxyip:\\/\\//i, '').trim();\n\t\tconst checkerUrl = proxyip\n\t\t\t? '/admin/proxyip-checker/' + encodeURIComponent(proxyip)\n\t\t\t: '/admin/proxyip-checker';\n\t\ttab.location.href = checkerUrl;\n\t};\n"""
if old not in s:
    raise SystemExit('openProxyIpChecker block not found or already changed')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
