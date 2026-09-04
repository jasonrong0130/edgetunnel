from pathlib import Path

p = Path('_worker.js')
s = p.read_text(encoding='utf-8')

# 1) Allow an alternate UUID at the VLESS parser level. It is only supplied by
# the WS handler on the restricted probe path.
old = "function 解析魏烈思请求(chunk, token) {\n\tconst data = 数据转Uint8Array(chunk);\n\tconst length = data.byteLength;\n\tif (length < 24) return { hasError: true, message: 'Invalid data' };\n\tconst version = data[0];\n\tif (!UUID字节匹配(data, 1, token)) return { hasError: true, message: 'Invalid uuid' };"
new = "function 解析魏烈思请求(chunk, token, alternateToken = '') {\n\tconst data = 数据转Uint8Array(chunk);\n\tconst length = data.byteLength;\n\tif (length < 24) return { hasError: true, message: 'Invalid data' };\n\tconst version = data[0];\n\tconst 主UUID匹配 = UUID字节匹配(data, 1, token);\n\tconst 备用UUID匹配 = !主UUID匹配 && alternateToken && UUID字节匹配(data, 1, alternateToken);\n\tif (!主UUID匹配 && !备用UUID匹配) return { hasError: true, message: 'Invalid uuid' };"
assert old in s, 'VLESS parser anchor not found'
s = s.replace(old, new, 1)

# 2) WS handler accepts an optional probe policy.
old = "async function 处理WS请求(request, yourUUID, url, 反代上下文 = {}) {"
new = "async function 处理WS请求(request, yourUUID, url, 反代上下文 = {}, EDT探针配置 = null) {"
assert old in s, 'WS signature anchor not found'
s = s.replace(old, new, 1)

# Only patch the WS handler body, never gRPC/XHTTP.
ws_start = s.index(new)
next_handler = s.find('async function 处理gRPC请求', ws_start)
if next_handler < 0:
    next_handler = s.find('async function ', ws_start + len(new))
assert next_handler > ws_start, 'next handler anchor not found'
ws = s[ws_start:next_handler]
needle = "const 解析结果 = 解析魏烈思请求(bytes, yourUUID);"
assert ws.count(needle) == 1, f'unexpected WS VLESS parse count: {ws.count(needle)}'
replacement = "const 解析结果 = 解析魏烈思请求(bytes, yourUUID, EDT探针配置?.uuid || '');\n\t\t\tconst 使用EDT探针UUID = !!(EDT探针配置?.uuid && !UUID字节匹配(bytes, 1, yourUUID) && UUID字节匹配(bytes, 1, EDT探针配置.uuid));"
ws = ws.replace(needle, replacement, 1)

# Restrict the alternate probe UUID to the single fixed TCP/TLS target.
needle2 = "const { port, hostname, version, isUDP, rawClientData } = 解析结果;\n\t\t\tconst respHeader = new Uint8Array([version, 0]);"
assert needle2 in ws, 'WS parsed target anchor not found'
replacement2 = "const { port, hostname, version, isUDP, rawClientData } = 解析结果;\n\t\t\tif (使用EDT探针UUID) {\n\t\t\t\tconst 实际探针主机 = String(hostname || '').toLowerCase().replace(/\\.$/, '');\n\t\t\t\tif (isUDP || 实际探针主机 !== EDT探针配置.targetHost || Number(port) !== EDT探针配置.targetPort) {\n\t\t\t\t\tthrow new Error('EDT probe UUID target is restricted');\n\t\t\t\t}\n\t\t\t}\n\t\t\tconst respHeader = new Uint8Array([version, 0]);"
ws = ws.replace(needle2, replacement2, 1)
s = s[:ws_start] + ws + s[next_handler:]

# 3) Build probe policy from Cloudflare env. It is deliberately never written
# into subscriptions/config_JSON.
anchor = "\t\tconst userID = (envUUID && uuidRegex.test(envUUID)) ? envUUID.toLowerCase() : [userIDMD5.slice(0, 8), userIDMD5.slice(8, 12), '4' + userIDMD5.slice(13, 16), '8' + userIDMD5.slice(17, 20), userIDMD5.slice(20)].join('-');"
assert anchor in s, 'userID anchor not found'
addition = anchor + "\n\t\tconst EDT探针UUID原始值 = String(env.EDT_PROBE_UUID || '').trim().toLowerCase();\n\t\tconst EDT探针目标主机 = String(env.EDT_PROBE_TARGET_HOST || 'www.cloudflare.com').trim().toLowerCase().replace(/\\.$/, '') || 'www.cloudflare.com';\n\t\tconst EDT探针目标端口数值 = Number(env.EDT_PROBE_TARGET_PORT || 443);\n\t\tconst EDT探针配置 = uuidRegex.test(EDT探针UUID原始值) && EDT探针UUID原始值 !== userID\n\t\t\t? { uuid: EDT探针UUID原始值, targetHost: EDT探针目标主机, targetPort: Number.isInteger(EDT探针目标端口数值) && EDT探针目标端口数值 >= 1 && EDT探针目标端口数值 <= 65535 ? EDT探针目标端口数值 : 443 }\n\t\t\t: null;"
s = s.replace(anchor, addition, 1)

# 4) Supply alternate UUID only on a forceproxyip WS route.
old_call = "\t\t\treturn await 处理WS请求(request, userID, url, 反代上下文);"
new_call = "\t\t\tconst 当前请求允许EDT探针 = !!(EDT探针配置 && /\\/forceproxyip=[^?#\\s]+/i.test(url.pathname));\n\t\t\treturn await 处理WS请求(request, userID, url, 反代上下文, 当前请求允许EDT探针 ? EDT探针配置 : null);"
assert old_call in s, 'WS call anchor not found'
s = s.replace(old_call, new_call, 1)

p.write_text(s, encoding='utf-8')
print('patched EDT probe UUID support')
