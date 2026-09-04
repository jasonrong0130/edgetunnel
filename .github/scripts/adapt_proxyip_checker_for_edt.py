from pathlib import Path

p = Path('proxyip-checker-source.js')
s = p.read_text(encoding='utf-8-sig')


def replace_once(old, new, label):
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly 1 match, got {count}')
    s = s.replace(old, new, 1)

# Make the result object distinguish real EDT chain reachability from exit-IP metadata.
replace_once(
"""\t\t\t\t\t\tconst buildResult = (\n\t\t\t\t\t\t\tok,\n\t\t\t\t\t\t\tresultStatusCode,\n\t\t\t\t\t\t\terror,\n\t\t\t\t\t\t\t{ exit = null } = {}\n\t\t\t\t\t\t) => ({\n\n\t\t\t\t\t\t\tcandidate: candidate.raw,\n\t\t\t\t\t\t\tconnect_ms: connectMs,\n\t\t\t\t\t\t\ttls_ms: tlsMs,\n\t\t\t\t\t\t\thttp_ms: httpMs,\n\t\t\t\t\t\t\tstatus_code: resultStatusCode,\n\t\t\t\t\t\t\tok,\n\t\t\t\t\t\t\terror,\n\t\t\t\t\t\t\texit,\n\t\t\t\t\t\t});\n""",
"""\t\t\t\t\t\tconst buildResult = (\n\t\t\t\t\t\t\tok,\n\t\t\t\t\t\t\tresultStatusCode,\n\t\t\t\t\t\t\terror,\n\t\t\t\t\t\t\t{ exit = null, cloudflareReached = false, chainVerified = false } = {}\n\t\t\t\t\t\t) => ({\n\n\t\t\t\t\t\t\tcandidate: candidate.raw,\n\t\t\t\t\t\t\tprobe_host: target.host,\n\t\t\t\t\t\t\tconnect_ms: connectMs,\n\t\t\t\t\t\t\ttls_ms: tlsMs,\n\t\t\t\t\t\t\thttp_ms: httpMs,\n\t\t\t\t\t\t\tstatus_code: resultStatusCode,\n\t\t\t\t\t\t\tok,\n\t\t\t\t\t\t\tcloudflare_reached: cloudflareReached,\n\t\t\t\t\t\t\tchain_verified: chainVerified,\n\t\t\t\t\t\t\terror,\n\t\t\t\t\t\t\texit,\n\t\t\t\t\t\t});\n""",
'buildResult block')

# EDT mode: a valid HTTP response from the intended Cloudflare probe proves the
# TCP -> SNI/TLS -> Cloudflare path works. 403/404 are therefore reachable,
# not failures. Exit JSON remains optional metadata.
replace_once(
"""\t\t\t\t\t\t\tif (statusCode !== 200) {\n\t\t\t\t\t\t\t\tconst bodyPreview = responseText ? ` body: ${responseText.slice(0, 120)}` : '';\n\t\t\t\t\t\t\t\treturn buildResult(false, statusCode, `unexpected status: ${statusCode ?? 'unknown'}${bodyPreview}`);\n\t\t\t\t\t\t\t}\n\n\t\t\t\t\t\t\tlet payload;\n\t\t\t\t\t\t\ttry {\n\t\t\t\t\t\t\t\tpayload = JSON.parse(responseText);\n\t\t\t\t\t\t\t} catch (error) {\n\t\t\t\t\t\t\t\treturn buildResult(false, statusCode, `invalid json response: ${String(error?.message || error)}`);\n\t\t\t\t\t\t\t}\n\n\t\t\t\t\t\t\tif (!pickExitIp(payload)) return buildResult(false, statusCode, 'probe json missing exit ip');\n\t\t\t\t\t\t\treturn buildResult(true, statusCode, null, { exit: payload });\n""",
"""\t\t\t\t\t\t\tconst hasHttpResponse = Number.isInteger(statusCode) && statusCode >= 100 && statusCode <= 599;\n\t\t\t\t\t\t\tconst cloudflareHeader = /(?:^|\\r\\n)(?:server:\\s*cloudflare\\b|cf-ray:\\s*[^\\r\\n]+)/i.test(headerText);\n\t\t\t\t\t\t\tlet payload = null;\n\t\t\t\t\t\t\tlet exit = null;\n\n\t\t\t\t\t\t\tif (statusCode === 200 && responseText) {\n\t\t\t\t\t\t\t\ttry {\n\t\t\t\t\t\t\t\t\tpayload = JSON.parse(responseText);\n\t\t\t\t\t\t\t\t\tif (pickExitIp(payload)) exit = payload;\n\t\t\t\t\t\t\t\t} catch (_) {\n\t\t\t\t\t\t\t\t\t// EDT 可用性不依赖探针 JSON；HTTP + Cloudflare 响应已足够证明 SNI/TLS 中转链路。\n\t\t\t\t\t\t\t\t}\n\t\t\t\t\t\t\t}\n\n\t\t\t\t\t\t\tconst cloudflareReached = cloudflareHeader || Boolean(exit);\n\t\t\t\t\t\t\tif (hasHttpResponse && cloudflareReached) {\n\t\t\t\t\t\t\t\tconst note = statusCode === 200\n\t\t\t\t\t\t\t\t\t? (exit ? null : 'HTTP 200 reached Cloudflare; exit metadata unavailable')\n\t\t\t\t\t\t\t\t\t: `HTTP ${statusCode} reached Cloudflare; EDT SNI/TLS chain verified`;\n\t\t\t\t\t\t\t\treturn buildResult(true, statusCode, note, { exit, cloudflareReached: true, chainVerified: true });\n\t\t\t\t\t\t\t}\n\n\t\t\t\t\t\t\tif (!hasHttpResponse) return buildResult(false, statusCode, 'no valid HTTP response after TLS handshake');\n\t\t\t\t\t\t\treturn buildResult(false, statusCode, `HTTP ${statusCode} received, but Cloudflare probe was not verified`);\n""",
'HTTP success criteria')

replace_once(
"""\t\t\t\treturn {\n\t\t\t\t\tcandidate: rawCandidate,\n\t\t\t\t\tsuccess: probeResults.some((result) => result.ok),\n\t\t\t\t\tproxyIP: candidate.hostname,\n\t\t\t\t\tportRemote: candidate.port,\n\t\t\t\t\tinferred_stack: inferredStack,\n\t\t\t\t\tsupports_ipv4: hasIPv4,\n\t\t\t\t\tsupports_ipv6: hasIPv6,\n\t\t\t\t\tdual_stack: inferredStack === 'dual_stack',\n\t\t\t\t\tresponseTime,\n\t\t\t\t\tcolo: req.cf?.colo || 'CF',\n\t\t\t\t\ttimeStamp: new Date().toISOString(),\n\t\t\t\t\tprobe_results: displayedProbeResults,\n\t\t\t\t};\n""",
"""\t\t\t\tconst edtChainOk = probeResults.some((result) => result?.chain_verified === true);\n\t\t\t\treturn {\n\t\t\t\t\tcandidate: rawCandidate,\n\t\t\t\t\tsuccess: edtChainOk,\n\t\t\t\t\tedt_chain_ok: edtChainOk,\n\t\t\t\t\tvalidation_mode: 'edt_sni_tls_http',\n\t\t\t\t\tcloudflare_reached: probeResults.some((result) => result?.cloudflare_reached === true),\n\t\t\t\t\tproxyIP: candidate.hostname,\n\t\t\t\t\tportRemote: candidate.port,\n\t\t\t\t\tinferred_stack: inferredStack,\n\t\t\t\t\tsupports_ipv4: hasIPv4,\n\t\t\t\t\tsupports_ipv6: hasIPv6,\n\t\t\t\t\tdual_stack: inferredStack === 'dual_stack',\n\t\t\t\t\tresponseTime,\n\t\t\t\t\tcolo: req.cf?.colo || 'CF',\n\t\t\t\t\ttimeStamp: new Date().toISOString(),\n\t\t\t\t\tprobe_results: displayedProbeResults,\n\t\t\t\t};\n""",
'candidate result block')

# UI: distinguish chain availability from optional exit metadata.
replace_once(
"""\t\t\t\t\titemObj.info.innerHTML =\n\t\t\t\t\t\t'<span class=\"result-label\">候选目标</span>' +\n\t\t\t\t\t\tbuildCopyableTarget(data.candidate || target) +\n\t\t\t\t\t\t'<span class=\"result-detail\">代理验证通过，可继续查看出口位置、网络信息和地图分布。</span>';\n\n\t\t\t\t\tconst metaParts = [\n\t\t\t\t\t\tbuildMetaChip(locations, 'location'),\n\t\t\t\t\t\tbuildMetaChip(networks, 'network'),\n\t\t\t\t\t\tbuildMetaChip(exitIps.length + '个出口', 'exits')\n\t\t\t\t\t];\n\t\t\t\t\titemObj.meta.innerHTML = metaParts.join('');\n""",
"""\t\t\t\t\tconst successfulProbes = Object.values(data.probe_results || {}).filter(function (probe) {\n\t\t\t\t\t\treturn probe && probe.ok;\n\t\t\t\t\t});\n\t\t\t\t\tconst statusText = Array.from(new Set(successfulProbes\n\t\t\t\t\t\t.map(function (probe) { return probe.status_code ? 'HTTP ' + probe.status_code : ''; })\n\t\t\t\t\t\t.filter(Boolean))).join(' / ');\n\t\t\t\t\tconst detailText = exitIps.length\n\t\t\t\t\t\t? 'EDT ProxyIP 链路验证通过，并获取到出口信息。'\n\t\t\t\t\t\t: 'EDT ProxyIP 链路验证通过：TCP、SNI/TLS 与 Cloudflare 响应正常' + (statusText ? '（' + statusText + '）' : '') + '。';\n\n\t\t\t\t\titemObj.info.innerHTML =\n\t\t\t\t\t\t'<span class=\"result-label\">候选目标</span>' +\n\t\t\t\t\t\tbuildCopyableTarget(data.candidate || target) +\n\t\t\t\t\t\t'<span class=\"result-detail\">' + detailText + '</span>';\n\n\t\t\t\t\tconst metaParts = [buildMetaChip('EDT链路可用', 'info')];\n\t\t\t\t\tif (statusText) metaParts.push(buildMetaChip(statusText, 'info'));\n\t\t\t\t\tif (exitIps.length) {\n\t\t\t\t\t\tmetaParts.push(buildMetaChip(locations, 'location'));\n\t\t\t\t\t\tmetaParts.push(buildMetaChip(networks, 'network'));\n\t\t\t\t\t\tmetaParts.push(buildMetaChip(exitIps.length + '个出口', 'exits'));\n\t\t\t\t\t} else {\n\t\t\t\t\t\tmetaParts.push(buildMetaChip('未返回出口 JSON，不影响 EDT 链路可用性', 'info'));\n\t\t\t\t\t}\n\t\t\t\t\titemObj.meta.innerHTML = metaParts.join('');\n""",
'frontend success block')

replace_once(
"""\t\t\t\t\titemObj.info.innerHTML =\n\t\t\t\t\t\t'<span class=\"result-label\">候选目标</span>' +\n\t\t\t\t\t\tbuildCopyableTarget(target) +\n\t\t\t\t\t\t'<span class=\"result-detail\">无法通过该代理访问 Cloudflare，请更换目标后重试。</span>';\n""",
"""\t\t\t\t\titemObj.info.innerHTML =\n\t\t\t\t\t\t'<span class=\"result-label\">候选目标</span>' +\n\t\t\t\t\t\tbuildCopyableTarget(target) +\n\t\t\t\t\t\t'<span class=\"result-detail\">未完成 EDT 所需的 TCP / SNI / TLS / Cloudflare 响应验证；请查看错误信息定位失败阶段。</span>';\n""",
'frontend failure text')

# Explain the EDT-specific acceptance criteria in the visible guide.
replace_once(
"""\t\t\t\t\t\t<ul class=\"guide-list\">\n\t\t\t\t\t\t\t<li>能够成功建立代理到指定端口（通常为 443）的 TCP 连接</li>\n\t\t\t\t\t\t\t<li>具备反向代理 Cloudflare IP 段的 HTTPS 服务能力</li>\n\t\t\t\t\t\t</ul>\n""",
"""\t\t\t\t\t\t<ul class=\"guide-list\">\n\t\t\t\t\t\t\t<li>Worker 能够连接候选 ProxyIP 的指定端口（通常为 443）</li>\n\t\t\t\t\t\t\t<li>通过该 ProxyIP 发送指定 SNI 后能够完成 TLS，并收到 Cloudflare 目标的有效 HTTP 响应</li>\n\t\t\t\t\t\t\t<li>HTTP 200、301、403、404 等响应都可以证明中转链路已到达目标；出口 JSON 只作为附加信息</li>\n\t\t\t\t\t\t</ul>\n""",
'guide criteria')

replace_once(
"""\t\t\t\t<div class=\"guide-tip\">\n\t\t\t\t\t<strong>这页检测的意义：</strong>本工具不是只做静态解析，而是尽量模拟真实链路去验证目标是否真的可用，帮助你更快筛掉“看起来在线、实际不可做代理”的候选 IP。\n\t\t\t\t</div>\n""",
"""\t\t\t\t<div class=\"guide-tip\">\n\t\t\t\t\t<strong>EDT 检测标准：</strong>这里优先判断真实中转链路是否建立成功。只要 TCP、SNI/TLS 正常并确认已经到达 Cloudflare，哪怕探针返回 403/404，也会判定为 EDT ProxyIP 可用；只有拿到 200 JSON 时才额外展示出口 IP、ASN 和地图信息。\n\t\t\t\t</div>\n""",
'guide tip')

# Add a small provenance note without pretending this is upstream behavior.
marker = "// Integrated for EDT admin ProxyIP checking; see THIRD_PARTY_LICENSES/CF-Workers-CheckProxyIP-LICENSE.\n"
if marker not in s:
    raise SystemExit('vendored header marker not found')
s = s.replace(marker, marker + "// EDT adaptation: availability is based on TCP + SNI/TLS + verified Cloudflare HTTP reachability; exit JSON is optional.\n", 1)

p.write_text(s, encoding='utf-8')
