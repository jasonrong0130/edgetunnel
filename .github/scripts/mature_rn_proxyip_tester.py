from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
app_path = root / 'tools/rn-proxyip-tester/app.py'
html_path = root / 'tools/rn-proxyip-tester/static/index.html'
readme_path = root / 'tools/rn-proxyip-tester/README.md'

app = app_path.read_text(encoding='utf-8')

new_run_job = r'''async def run_job(job):
    targets = job["targets"]
    settings = job["settings"]
    check_sem = asyncio.Semaphore(settings["check_concurrency"])
    job["results"] = [
        {"input": raw, "candidate": raw, "available": None, "state": "pending"}
        for raw in targets
    ]
    index_by_target = {raw: idx for idx, raw in enumerate(targets)}
    job["state"] = "checking"
    job["started_at"] = time.time()
    persist_job(job)

    async def wrapped_check(raw):
        if job.get("cancel_requested"):
            return
        async with check_sem:
            if job.get("cancel_requested"):
                return
            idx = index_by_target[raw]
            job["results"][idx]["state"] = "checking"
            result = await test_one(raw, settings["generic_test"], settings["timeout"])
            result["state"] = "checked"
            job["results"][idx] = result
            job["completed"] += 1
            if result.get("available"):
                job["available"] += 1
            if result.get("generic_ok") is True:
                job["generic_available"] += 1
            if result.get("exit_match") == "same":
                job["same_exit"] += 1

    tasks = [asyncio.create_task(wrapped_check(raw)) for raw in targets]
    await asyncio.gather(*tasks, return_exceptions=True)

    if job.get("cancel_requested"):
        for row in job["results"]:
            if row.get("state") in ("pending", "checking"):
                row["state"] = "cancelled"
        job["state"] = "cancelled"
        job["finished_at"] = time.time()
        persist_job(job)
        return

    ordered = job["results"]
    speed_cfg = settings["speed"]
    if speed_cfg["enabled"]:
        speed_targets = [r for r in ordered if r.get("available")]
        speed_targets.sort(key=lambda r: (r.get("tcp_ms") is None, r.get("tcp_ms") or 10**9))
        if speed_cfg.get("limit", 0) > 0:
            speed_targets = speed_targets[:speed_cfg["limit"]]
        job["speed_total"] = len(speed_targets)
        job["state"] = "speeding"
        job["speed_started_at"] = time.time()
        persist_job(job)
        speed_sem = asyncio.Semaphore(speed_cfg["concurrency"])

        async def wrapped_speed(result):
            if job.get("cancel_requested"):
                return
            async with speed_sem:
                if job.get("cancel_requested"):
                    return
                result["state"] = "speeding"
                runs = []
                for _ in range(speed_cfg["repeats"]):
                    if job.get("cancel_requested"):
                        break
                    runs.append(await speed_test(result["host"], result["port"], speed_cfg["bytes"], max(settings["timeout"], 15.0)))
                good = [r["mbps"] for r in runs if r.get("ok") and isinstance(r.get("mbps"), (int, float))]
                result["speed_runs"] = runs
                result["speed_success"] = len(good)
                result["speed_mbps_avg"] = round(sum(good) / len(good), 2) if good else None
                result["speed_mbps_min"] = round(min(good), 2) if good else None
                result["speed_mbps_max"] = round(max(good), 2) if good else None
                result["state"] = "done" if not job.get("cancel_requested") else "cancelled"
                job["speed_completed"] += 1
                if result.get("speed_mbps_avg") is not None and result["speed_mbps_avg"] >= 100:
                    job["high_speed"] += 1

        speed_tasks = [asyncio.create_task(wrapped_speed(r)) for r in speed_targets]
        await asyncio.gather(*speed_tasks, return_exceptions=True)

    if job.get("cancel_requested"):
        job["state"] = "cancelled"
    else:
        job["state"] = "done"
        for row in job["results"]:
            if row.get("state") == "checked":
                row["state"] = "done"
    job["finished_at"] = time.time()
    persist_job(job)
'''

app, n = re.subn(r'async def run_job\(job\):.*?(?=\ndef persist_job\(job\):)', new_run_job + '\n', app, flags=re.S)
assert n == 1, f'run_job replacement count={n}'

old_settings = '''            "enabled": bool(speed.get("enabled", True)),
            "concurrency": clamp_int(speed.get("concurrency"), DEFAULT_SPEED_CONCURRENCY, 1, 10),
            "bytes": clamp_int(speed.get("bytes"), DEFAULT_SPEED_BYTES, 1024 * 1024, 50 * 1024 * 1024),
            "repeats": clamp_int(speed.get("repeats"), DEFAULT_SPEED_REPEATS, 1, 5),
'''
new_settings = '''            "enabled": bool(speed.get("enabled", True)),
            "concurrency": clamp_int(speed.get("concurrency"), DEFAULT_SPEED_CONCURRENCY, 1, 10),
            "bytes": clamp_int(speed.get("bytes"), DEFAULT_SPEED_BYTES, 1024 * 1024, 50 * 1024 * 1024),
            "repeats": clamp_int(speed.get("repeats"), DEFAULT_SPEED_REPEATS, 1, 5),
            "limit": clamp_int(speed.get("limit"), 0, 0, MAX_TARGETS),
'''
assert old_settings in app
app = app.replace(old_settings, new_settings, 1)

old_job = '''        "id": job_id, "state": "queued", "created_at": time.time(), "finished_at": None,
        "total": len(targets), "completed": 0, "available": 0, "same_exit": 0,
        "speed_total": 0, "speed_completed": 0, "settings": settings,
        "targets": targets, "results": [],
'''
new_job = '''        "id": job_id, "state": "queued", "created_at": time.time(), "started_at": None,
        "speed_started_at": None, "finished_at": None, "cancel_requested": False,
        "total": len(targets), "completed": 0, "available": 0, "generic_available": 0, "same_exit": 0,
        "speed_total": 0, "speed_completed": 0, "high_speed": 0, "settings": settings,
        "targets": targets, "results": [],
'''
assert old_job in app
app = app.replace(old_job, new_job, 1)

insert_after_health = '''@app.get("/health")
async def health():
    return {"ok": True, "jobs": len(JOBS), "token_configured": bool(TOKEN)}
'''
extra_routes = r'''

@app.get("/api/jobs")
async def list_jobs(authorization: Optional[str] = Header(None), x_api_token: Optional[str] = Header(None)):
    require_token(authorization, x_api_token)
    snapshots = {}
    for job_id, job in JOBS.items():
        snapshots[job_id] = job
    for path in DATA_DIR.glob("*.json"):
        if path.stem in snapshots:
            continue
        try:
            snapshots[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    rows = []
    for job in snapshots.values():
        rows.append({
            "id": job.get("id"), "state": job.get("state"), "created_at": job.get("created_at"),
            "finished_at": job.get("finished_at"), "total": job.get("total", 0),
            "completed": job.get("completed", 0), "available": job.get("available", 0),
            "same_exit": job.get("same_exit", 0), "speed_completed": job.get("speed_completed", 0),
            "high_speed": job.get("high_speed", 0),
        })
    rows.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
    return {"jobs": rows[:30]}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, authorization: Optional[str] = Header(None), x_api_token: Optional[str] = Header(None)):
    require_token(authorization, x_api_token)
    job = JOBS.get(job_id)
    if not job:
        job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("state") in ("done", "cancelled"):
        return {"id": job_id, "state": job.get("state"), "cancel_requested": False}
    job["cancel_requested"] = True
    JOBS[job_id] = job
    persist_job(job)
    return {"id": job_id, "state": job.get("state"), "cancel_requested": True}
'''
assert insert_after_health in app
app = app.replace(insert_after_health, insert_after_health + extra_routes, 1)

app_path.write_text(app, encoding='utf-8')

html = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark">
<title>ProxyIP Scanner · RN</title>
<style>
:root{--bg:#07111f;--panel:#0c1828;--panel2:#101f32;--line:#1e3147;--text:#eef6ff;--muted:#8195ad;--cyan:#39d6ff;--green:#39e58c;--yellow:#f7c948;--red:#ff6b7a;--blue:#5d8cff;--shadow:0 18px 55px rgba(0,0,0,.22);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;color:var(--text);background:radial-gradient(circle at 15% -10%,rgba(57,214,255,.12),transparent 34%),radial-gradient(circle at 90% 0,rgba(93,140,255,.10),transparent 30%),var(--bg);min-height:100vh}button,input,textarea,select{font:inherit}button{cursor:pointer}.app{max-width:1640px;margin:auto;padding:22px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px}.logo{width:42px;height:42px;border:1px solid rgba(57,214,255,.42);border-radius:13px;background:linear-gradient(145deg,rgba(57,214,255,.18),rgba(93,140,255,.08));display:grid;place-items:center;box-shadow:inset 0 0 28px rgba(57,214,255,.07)}.logo:before{content:"";width:19px;height:19px;border:2px solid var(--cyan);border-radius:50%;box-shadow:0 0 16px rgba(57,214,255,.45)}h1{font-size:20px;margin:0;letter-spacing:.2px}.brand p{margin:3px 0 0;color:var(--muted);font-size:12px}.statusline{display:flex;gap:9px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.pill{border:1px solid var(--line);background:rgba(12,24,40,.8);padding:7px 10px;border-radius:999px;color:var(--muted);font-size:12px}.pill.live{color:var(--green);border-color:rgba(57,229,140,.28)}.pill .dot{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block;margin-right:7px;box-shadow:0 0 8px currentColor}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:16px}.panel{background:linear-gradient(180deg,rgba(16,31,50,.96),rgba(10,23,39,.96));border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}.scan-panel{padding:18px}.panel-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:14px}.kicker{text-transform:uppercase;font-size:10px;letter-spacing:1.7px;color:var(--cyan);font-weight:800}.panel h2{font-size:16px;margin:4px 0 0}.hint{color:var(--muted);font-size:12px;line-height:1.55}.input-wrap{position:relative}.editor{width:100%;min-height:220px;resize:vertical;border:1px solid #263d57;background:#071321;color:#dbeaff;border-radius:13px;padding:14px 14px 42px;outline:none;font-family:"SFMono-Regular",Consolas,monospace;font-size:13px;line-height:1.55}.editor:focus{border-color:rgba(57,214,255,.65);box-shadow:0 0 0 3px rgba(57,214,255,.07)}.editor-foot{position:absolute;bottom:9px;left:12px;right:12px;display:flex;justify-content:space-between;pointer-events:none;color:var(--muted);font-size:11px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.btn{border:1px solid transparent;border-radius:10px;padding:9px 13px;font-weight:700;color:#06121d;background:var(--cyan)}.btn:hover{filter:brightness(1.06)}.btn.secondary{background:#15273b;border-color:#294059;color:#dceaff}.btn.danger{background:rgba(255,107,122,.12);color:#ff9aa5;border-color:rgba(255,107,122,.28)}.btn:disabled{opacity:.42;cursor:not-allowed}.small{font-size:12px;padding:7px 10px}.filebtn input{display:none}
.config{padding:18px}.config-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.field{min-width:0}.field.full{grid-column:1/-1}.field label{display:flex;justify-content:space-between;color:#91a6bc;font-size:11px;margin:0 0 6px}.control{width:100%;height:39px;border-radius:9px;border:1px solid #294059;background:#091726;color:#eaf5ff;padding:0 10px;outline:none}.control:focus{border-color:var(--cyan)}.switchrow{display:flex;align-items:center;justify-content:space-between;border:1px solid #294059;background:#091726;border-radius:9px;padding:9px 10px;font-size:12px}.switchrow input{accent-color:var(--cyan)}.preset-row{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:12px}.preset{background:#0a1726;border:1px solid #294059;color:#9db0c5;border-radius:9px;padding:9px 5px;font-size:11px}.preset.active{color:var(--cyan);border-color:rgba(57,214,255,.55);background:rgba(57,214,255,.07)}.estimate{margin-top:12px;padding:10px;border-radius:10px;background:#081522;border:1px dashed #2b435d;color:#8fa6bc;font-size:11px;line-height:1.65}.estimate strong{color:#d8edff}
.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-top:16px}.metric{padding:13px 14px;background:rgba(9,22,37,.9);border:1px solid var(--line);border-radius:13px}.metric .v{font-size:23px;font-weight:800;letter-spacing:-.5px}.metric .l{color:var(--muted);font-size:11px;margin-top:3px}.metric.good .v{color:var(--green)}.metric.cyan .v{color:var(--cyan)}.metric.yellow .v{color:var(--yellow)}
.progress-card{margin-top:10px;background:#091625;border:1px solid var(--line);border-radius:13px;padding:12px}.progress-top{display:flex;justify-content:space-between;gap:12px;font-size:11px;color:var(--muted);margin-bottom:8px}.track{height:7px;border-radius:999px;background:#14273b;overflow:hidden}.bar{height:100%;width:0;background:linear-gradient(90deg,var(--cyan),var(--blue));transition:width .25s ease}.stage-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:9px}.stage{font-size:11px;color:#8ca1b8}.stage b{color:#ddecfa;font-weight:700}.stage-track{height:4px;background:#13263a;border-radius:99px;margin-top:5px;overflow:hidden}.stage-track i{display:block;height:100%;width:0;background:var(--green)}
.results{margin-top:16px}.results-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:14px 15px;border-bottom:1px solid var(--line)}.filters{display:flex;gap:7px;flex-wrap:wrap}.filters .control{height:34px;width:auto;min-width:120px;font-size:11px}.search{min-width:210px!important}.table-wrap{overflow:auto;max-height:620px}.table{border-collapse:collapse;width:100%;font-size:11.5px;white-space:nowrap}.table th,.table td{padding:9px 10px;border-bottom:1px solid rgba(30,49,71,.72);text-align:left}.table th{position:sticky;top:0;z-index:2;background:#0d1b2c;color:#8fa5bc;font-size:10.5px;text-transform:uppercase;letter-spacing:.25px}.table tr:hover td{background:rgba(57,214,255,.025)}.candidate{font-family:Consolas,monospace;color:#d8ecff;font-weight:700}.badge{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:99px;font-size:10px;font-weight:800;border:1px solid}.badge.ok{color:var(--green);border-color:rgba(57,229,140,.25);background:rgba(57,229,140,.07)}.badge.no{color:var(--red);border-color:rgba(255,107,122,.25);background:rgba(255,107,122,.07)}.badge.wait{color:#90a6bd;border-color:#2a425d}.badge.warn{color:var(--yellow);border-color:rgba(247,201,72,.28);background:rgba(247,201,72,.06)}.speed{font-weight:900;color:var(--cyan)}.err{max-width:260px;overflow:hidden;text-overflow:ellipsis;color:#ff8793}.pager{display:flex;align-items:center;justify-content:space-between;padding:11px 14px;border-top:1px solid var(--line);color:var(--muted);font-size:11px}.pager-actions{display:flex;gap:6px}.empty{padding:44px;text-align:center;color:#71879f}
.side{display:flex;flex-direction:column;gap:16px}.side .panel{padding:15px}.toplist{display:flex;flex-direction:column;gap:7px;margin-top:11px}.topitem{display:grid;grid-template-columns:28px minmax(0,1fr) auto;align-items:center;gap:8px;padding:9px;border:1px solid var(--line);background:#091725;border-radius:10px}.rank{width:24px;height:24px;border-radius:7px;background:#14283d;display:grid;place-items:center;color:#91a8bf;font-size:10px;font-weight:900}.topitem:nth-child(-n+3) .rank{color:#05131d;background:var(--cyan)}.topname{overflow:hidden;text-overflow:ellipsis;font-family:Consolas,monospace;font-size:10.5px}.topspeed{color:var(--green);font-weight:900;font-size:11px}.history{display:flex;flex-direction:column;gap:7px;margin-top:10px}.history-item{padding:9px;border:1px solid var(--line);border-radius:10px;background:#091725;cursor:pointer}.history-item:hover{border-color:#36516e}.history-top{display:flex;justify-content:space-between;gap:6px;font-size:11px}.history-sub{color:var(--muted);font-size:10px;margin-top:5px}.legend{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.legend div{padding:8px;border-radius:9px;background:#091725;color:#8fa4bb;font-size:10px}.legend b{display:block;color:#dbeeff;font-size:11px;margin-bottom:2px}.toast{position:fixed;right:22px;bottom:22px;padding:11px 14px;background:#102238;border:1px solid #32506f;border-radius:10px;box-shadow:var(--shadow);font-size:12px;opacity:0;transform:translateY(8px);pointer-events:none;transition:.2s;z-index:20}.toast.show{opacity:1;transform:none}.toast.error{border-color:rgba(255,107,122,.55);color:#ff9ba5}
@media(max-width:1180px){.layout{grid-template-columns:1fr}.side{display:grid;grid-template-columns:1fr 1fr}.metrics{grid-template-columns:repeat(3,1fr)}}@media(max-width:720px){.app{padding:12px}.topbar{align-items:flex-start}.statusline{display:none}.config-grid,.side,.stage-grid{grid-template-columns:1fr}.metrics{grid-template-columns:1fr 1fr}.results-head{align-items:flex-start;flex-direction:column}.filters{width:100%}.filters .control{width:100%}.editor{min-height:190px}.table-wrap{max-height:68vh}}
</style></head>
<body><div class="app">
<header class="topbar"><div class="brand"><div class="logo"></div><div><h1>ProxyIP Scanner</h1><p>RN Engine · 批量验证真实出口与链路测速</p></div></div><div class="statusline"><span class="pill live"><i class="dot"></i><span id="healthText">Engine Online</span></span><span class="pill" id="clock">--:--:--</span><span class="pill">v1.0</span></div></header>
<div class="layout"><main>
<section class="panel scan-panel"><div class="panel-head"><div><div class="kicker">Target Pool</div><h2>候选 ProxyIP</h2></div><div class="hint">每行一个，支持 IP / 域名与自定义端口；重复项会自动去除。</div></div><div class="input-wrap"><textarea class="editor" id="targets" spellcheck="false" placeholder="45.196.234.118:443&#10;1.2.3.4:443&#10;proxy.example.com:443"></textarea><div class="editor-foot"><span id="parseInfo">0 个候选</span><span>MAX 5000</span></div></div><div class="toolbar"><button class="btn" id="start">开始扫描 + 测速</button><button class="btn secondary" id="quick">只扫描</button><button class="btn danger" id="stop" disabled>停止任务</button><label class="btn secondary small filebtn">导入 TXT<input type="file" id="fileInput" accept=".txt,.csv,text/plain"></label><button class="btn secondary small" id="dedupe">整理去重</button><button class="btn secondary small" id="clear">清空</button></div></section>
<section class="metrics"><div class="metric"><div class="v" id="mTotal">0</div><div class="l">总候选</div></div><div class="metric cyan"><div class="v" id="mDone">0</div><div class="l">已扫描</div></div><div class="metric good"><div class="v" id="mAvail">0</div><div class="l">可用 ProxyIP</div></div><div class="metric good"><div class="v" id="mSame">0</div><div class="l">入口 = 出口</div></div><div class="metric yellow"><div class="v" id="mGeneric">0</div><div class="l">通用 SNI</div></div><div class="metric cyan"><div class="v" id="mFast">0</div><div class="l">≥ 100 Mbps</div></div></section>
<section class="progress-card"><div class="progress-top"><span id="stateText">等待任务</span><span id="rateText">0.0 IP/s · ETA --</span></div><div class="track"><div class="bar" id="mainBar"></div></div><div class="stage-grid"><div class="stage"><span>快速检测 <b id="checkStage">0 / 0</b></span><div class="stage-track"><i id="checkBar"></i></div></div><div class="stage"><span>链路测速 <b id="speedStage">0 / 0</b></span><div class="stage-track"><i id="speedBar"></i></div></div></div></section>
<section class="panel results"><div class="results-head"><div><div class="kicker">Live Results</div><h2>扫描结果</h2></div><div class="filters"><input class="control search" id="search" placeholder="搜索 IP / 出口 / 国家"><select class="control" id="filter"><option value="all">全部状态</option><option value="available">仅可用</option><option value="same">入口=出口</option><option value="generic">通用 SNI</option><option value="fast">≥100 Mbps</option><option value="failed">仅失败</option></select><select class="control" id="country"><option value="all">全部地区</option></select><select class="control" id="sort"><option value="default">原顺序</option><option value="speed">速度 ↓</option><option value="latency">延迟 ↑</option><option value="country">地区</option></select></div></div><div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>ProxyIP</th><th>状态</th><th>通用 SNI</th><th>TCP</th><th>TLS</th><th>HTTP</th><th>真实出口 IP</th><th>地区</th><th>CF</th><th>出口关系</th><th>平均速度</th><th>最低速度</th><th>稳定性</th><th>错误</th></tr></thead><tbody id="tbody"></tbody></table><div class="empty" id="empty">尚未开始扫描</div></div><div class="pager"><span id="pageInfo">0 条结果</span><div class="pager-actions"><button class="btn secondary small" id="prev">上一页</button><button class="btn secondary small" id="next">下一页</button></div></div></section>
</main><aside class="side">
<section class="panel config"><div class="panel-head"><div><div class="kicker">Scan Profile</div><h2>扫描参数</h2></div></div><div class="preset-row"><button class="preset" data-preset="fast">快速</button><button class="preset active" data-preset="balanced">均衡</button><button class="preset" data-preset="deep">深度</button></div><div class="config-grid"><div class="field full"><label>API Token <span>仅存本机浏览器</span></label><input class="control" id="token" type="password" autocomplete="off" placeholder="PROXY_TESTER_TOKEN"></div><div class="field"><label>检测并发</label><input class="control" id="checkConcurrency" type="number" value="50" min="1" max="200"></div><div class="field"><label>超时 (秒)</label><input class="control" id="timeout" type="number" value="7" min="2" max="20"></div><div class="field"><label>测速并发</label><input class="control" id="speedConcurrency" type="number" value="4" min="1" max="10"></div><div class="field"><label>测速上限</label><select class="control" id="speedLimit"><option value="0">全部可用</option><option value="20">最快前 20</option><option value="50">最快前 50</option><option value="100">最快前 100</option><option value="200">最快前 200</option></select></div><div class="field"><label>单次下载</label><select class="control" id="speedBytes"><option value="5242880">5 MiB</option><option value="10485760">10 MiB</option><option value="31457280">30 MiB</option><option value="52428800">50 MiB</option></select></div><div class="field"><label>重复次数</label><select class="control" id="speedRepeats"><option value="1">1 次</option><option value="3" selected>3 次</option><option value="5">5 次</option></select></div><div class="field full"><div class="switchrow"><span>验证通用 SNI（gstatic）</span><input id="generic" type="checkbox" checked></div></div></div><div class="estimate" id="estimate">预计测速流量：<strong>等待输入候选</strong><br>测速只对快速检测通过的节点执行。</div></section>
<section class="panel"><div class="panel-head"><div><div class="kicker">Top Performance</div><h2>TOP 高速节点</h2></div><button class="btn secondary small" id="copyTop">复制 TOP</button></div><div class="toplist" id="toplist"><div class="hint">完成测速后自动按平均速度排名。</div></div></section>
<section class="panel"><div class="panel-head"><div><div class="kicker">Actions</div><h2>结果操作</h2></div></div><div class="toolbar" style="margin-top:0"><button class="btn secondary small" id="copyVisible">复制当前结果</button><button class="btn secondary small" id="copyUsable">复制可用</button><button class="btn secondary small" id="csv">导出 CSV</button><button class="btn secondary small" id="txt">导出 TXT</button></div><div class="legend"><div><b>基础可用</b>TCP + TLS/SNI + Cloudflare Trace</div><div><b>真实出口</b>Trace 返回的公网来源 IP</div><div><b>入口=出口</b>候选 IP 与实际出口一致</div><div><b>通用 SNI</b>可继续代理非 CF HTTPS</div></div></section>
<section class="panel"><div class="panel-head"><div><div class="kicker">Recent Jobs</div><h2>历史任务</h2></div><button class="btn secondary small" id="refreshHistory">刷新</button></div><div class="history" id="history"><div class="hint">输入 Token 后显示最近 30 个任务。</div></div></section>
</aside></div></div><div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let currentJob=null,timer=null,lastData=null,page=1;const PAGE_SIZE=100;let filteredRows=[];let jobStart=0;
const stateMap={queued:'排队中',checking:'快速检测',speeding:'链路测速',done:'已完成',cancelled:'已停止'};
function toast(msg,error=false){const e=$('toast');e.textContent=msg;e.className='toast show'+(error?' error':'');clearTimeout(e._t);e._t=setTimeout(()=>e.className='toast',2400)}
function auth(json=false){const h={Authorization:'Bearer '+$('token').value.trim()};if(json)h['Content-Type']='application/json';return h}
function parseTargets(){const raw=$('targets').value.split(/[\n\r,\s]+/).map(v=>v.trim()).filter(Boolean);return [...new Set(raw)]}
function updateParse(){const n=parseTargets().length;$('parseInfo').textContent=n+' 个候选';updateEstimate(n)}
function updateEstimate(n=parseTargets().length){const bytes=Number($('speedBytes').value)||0,repeats=Number($('speedRepeats').value)||1,limit=Number($('speedLimit').value)||0;const maxNodes=limit?Math.min(n,limit):n;const gb=maxNodes*bytes*repeats/1024/1024/1024;$('estimate').innerHTML='理论最大测速流量：<strong>'+gb.toFixed(gb<10?2:1)+' GiB</strong><br>实际只对筛选通过的节点测速'+(limit?'，最多 '+limit+' 个。':'。')}
$('targets').addEventListener('input',updateParse);['speedBytes','speedRepeats','speedLimit'].forEach(id=>$(id).addEventListener('change',()=>updateEstimate()));
$('token').value=localStorage.getItem('rn_proxy_tester_token')||'';$('token').addEventListener('change',()=>{localStorage.setItem('rn_proxy_tester_token',$('token').value.trim());loadHistory()});
setInterval(()=>{$('clock').textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false})},1000);
fetch('/health').then(r=>r.json()).then(d=>{$('healthText').textContent=d.ok?'Engine Online':'Engine Error'}).catch(()=>{$('healthText').textContent='Engine Offline'});
const presets={fast:{check:100,timeout:4,speedc:6,bytes:5242880,repeats:1,limit:100},balanced:{check:50,timeout:7,speedc:4,bytes:5242880,repeats:3,limit:0},deep:{check:30,timeout:10,speedc:2,bytes:31457280,repeats:3,limit:0}};
document.querySelectorAll('.preset').forEach(b=>b.onclick=()=>{document.querySelectorAll('.preset').forEach(x=>x.classList.remove('active'));b.classList.add('active');const p=presets[b.dataset.preset];$('checkConcurrency').value=p.check;$('timeout').value=p.timeout;$('speedConcurrency').value=p.speedc;$('speedBytes').value=p.bytes;$('speedRepeats').value=p.repeats;$('speedLimit').value=String(p.limit);updateEstimate()});
$('dedupe').onclick=()=>{const arr=parseTargets();$('targets').value=arr.join('\n');updateParse();toast('已整理为 '+arr.length+' 个唯一候选')};$('clear').onclick=()=>{$('targets').value='';updateParse()};
$('fileInput').onchange=async e=>{const f=e.target.files[0];if(!f)return;const t=await f.text();$('targets').value=[$('targets').value,t].filter(Boolean).join('\n');$('dedupe').click();e.target.value=''};
function setRunning(on){$('start').disabled=on;$('quick').disabled=on;$('stop').disabled=!on}
async function start(speedEnabled){const token=$('token').value.trim(),targets=parseTargets();if(!token)return toast('请先填写 API Token',true);if(!targets.length)return toast('请先输入 ProxyIP 列表',true);localStorage.setItem('rn_proxy_tester_token',token);const payload={targets,check_concurrency:Number($('checkConcurrency').value)||50,timeout:Number($('timeout').value)||7,generic_test:$('generic').checked,speed:{enabled:speedEnabled,concurrency:Number($('speedConcurrency').value)||4,bytes:Number($('speedBytes').value),repeats:Number($('speedRepeats').value),limit:Number($('speedLimit').value)||0}};setRunning(true);lastData=null;page=1;jobStart=Date.now()/1000;try{const r=await fetch('/api/jobs',{method:'POST',headers:auth(true),body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)throw new Error(d.detail||'启动失败');currentJob=d.id;clearInterval(timer);await poll();timer=setInterval(poll,800);toast('任务已启动 · '+d.id)}catch(e){setRunning(false);toast(e.message,true)}}
$('start').onclick=()=>start(true);$('quick').onclick=()=>start(false);$('stop').onclick=async()=>{if(!currentJob)return;try{const r=await fetch('/api/jobs/'+currentJob+'/cancel',{method:'POST',headers:auth()});const d=await r.json();if(!r.ok)throw new Error(d.detail||'停止失败');$('stateText').textContent='正在停止任务…';toast('已发送停止请求')}catch(e){toast(e.message,true)}};
async function poll(){if(!currentJob)return;try{const r=await fetch('/api/jobs/'+currentJob,{headers:auth()});if(!r.ok)throw new Error('读取任务失败');const d=await r.json();lastData=d;render(d);if(['done','cancelled'].includes(d.state)){clearInterval(timer);setRunning(false);loadHistory();toast(d.state==='done'?'扫描任务完成':'任务已停止')}}catch(e){clearInterval(timer);setRunning(false);toast(e.message,true)}}
function pct(a,b){return b?Math.min(100,Math.round(a/b*100)):0}function fmtEta(sec){if(!isFinite(sec)||sec<0)return '--';if(sec<60)return Math.ceil(sec)+'s';if(sec<3600)return Math.ceil(sec/60)+'m';return (sec/3600).toFixed(1)+'h'}
function render(d){$('mTotal').textContent=d.total||0;$('mDone').textContent=d.completed||0;$('mAvail').textContent=d.available||0;$('mSame').textContent=d.same_exit||0;$('mGeneric').textContent=d.generic_available||0;$('mFast').textContent=d.high_speed||0;$('stateText').textContent=(stateMap[d.state]||d.state)+' · '+d.id;const checkPct=pct(d.completed,d.total),speedPct=pct(d.speed_completed,d.speed_total);$('checkBar').style.width=checkPct+'%';$('speedBar').style.width=speedPct+'%';$('checkStage').textContent=(d.completed||0)+' / '+(d.total||0);$('speedStage').textContent=(d.speed_completed||0)+' / '+(d.speed_total||0);const overall=d.state==='speeding'?50+speedPct/2:checkPct/2;$('mainBar').style.width=(d.state==='done'?100:d.state==='cancelled'?Math.max(checkPct/2,checkPct):overall)+'%';const started=d.started_at||jobStart||Date.now()/1000,elapsed=Math.max(Date.now()/1000-started,.1),rate=(d.completed||0)/elapsed;let remain=d.state==='checking'?((d.total-d.completed)/(rate||.0001)):0;if(d.state==='speeding'){const se=Math.max(Date.now()/1000-(d.speed_started_at||Date.now()/1000),.1),sr=(d.speed_completed||0)/se;remain=(d.speed_total-d.speed_completed)/(sr||.0001)}$('rateText').textContent=rate.toFixed(1)+' IP/s · ETA '+fmtEta(remain);updateCountries(d.results||[]);renderRows(d.results||[]);renderTop(d.results||[])}
function rowState(x){if(x.available===true)return '<span class="badge ok">● 可用</span>';if(x.available===false)return '<span class="badge no">● 失败</span>';if(x.state==='cancelled')return '<span class="badge warn">已停止</span>';return '<span class="badge wait">检测中</span>'}function boolBadge(v){return v===true?'<span class="badge ok">YES</span>':v===false?'<span class="badge no">NO</span>':'—'}function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}function val(v,s=''){return v===null||v===undefined||v===''?'—':esc(v)+s}
function applyFilters(rows){let list=rows.map((x,i)=>({...x,_idx:i+1})),f=$('filter').value,c=$('country').value,q=$('search').value.trim().toLowerCase();if(f==='available')list=list.filter(x=>x.available===true);if(f==='same')list=list.filter(x=>x.exit_match==='same');if(f==='generic')list=list.filter(x=>x.generic_ok===true);if(f==='fast')list=list.filter(x=>(x.speed_mbps_avg||0)>=100);if(f==='failed')list=list.filter(x=>x.available===false);if(c!=='all')list=list.filter(x=>x.country===c);if(q)list=list.filter(x=>[x.candidate,x.exit_ip,x.country,x.colo,x.error].some(v=>String(v||'').toLowerCase().includes(q)));const s=$('sort').value;if(s==='speed')list.sort((a,b)=>(b.speed_mbps_avg??-1)-(a.speed_mbps_avg??-1));if(s==='latency')list.sort((a,b)=>(a.tcp_ms??1e9)-(b.tcp_ms??1e9));if(s==='country')list.sort((a,b)=>String(a.country||'ZZ').localeCompare(String(b.country||'ZZ')));return list}
function renderRows(rows){filteredRows=applyFilters(rows);const pages=Math.max(1,Math.ceil(filteredRows.length/PAGE_SIZE));page=Math.min(page,pages);const start=(page-1)*PAGE_SIZE,list=filteredRows.slice(start,start+PAGE_SIZE);$('empty').style.display=list.length?'none':'block';$('tbody').innerHTML=list.map(x=>`<tr><td>${x._idx}</td><td class="candidate">${esc(x.candidate||x.input)}</td><td>${rowState(x)}</td><td>${boolBadge(x.generic_ok)}</td><td>${val(x.tcp_ms,' ms')}</td><td>${val(x.tls_ms,' ms')}</td><td>${val(x.http_status)}</td><td class="candidate">${val(x.exit_ip)}</td><td>${val(x.country)}</td><td>${val(x.colo)}</td><td>${x.exit_match==='same'?'<span class="badge ok">相同</span>':x.exit_match==='different'?'<span class="badge warn">不同</span>':'—'}</td><td class="speed">${val(x.speed_mbps_avg,' Mbps')}</td><td>${val(x.speed_mbps_min,' Mbps')}</td><td>${x.speed_runs?val(x.speed_success)+' / '+x.speed_runs.length:'—'}</td><td class="err" title="${esc(x.error||x.generic_error||'')}">${val(x.error||x.generic_error)}</td></tr>`).join('');$('pageInfo').textContent=filteredRows.length+' 条 · 第 '+page+' / '+pages+' 页';$('prev').disabled=page<=1;$('next').disabled=page>=pages}
['filter','country','sort'].forEach(id=>$(id).onchange=()=>{page=1;lastData&&renderRows(lastData.results||[])});$('search').oninput=()=>{page=1;lastData&&renderRows(lastData.results||[])};$('prev').onclick=()=>{page=Math.max(1,page-1);lastData&&renderRows(lastData.results||[])};$('next').onclick=()=>{page++;lastData&&renderRows(lastData.results||[])};
function updateCountries(rows){const current=$('country').value,cs=[...new Set(rows.map(x=>x.country).filter(Boolean))].sort();const html='<option value="all">全部地区</option>'+cs.map(c=>'<option value="'+esc(c)+'">'+esc(c)+'</option>').join('');if($('country').innerHTML!==html){$('country').innerHTML=html;if(cs.includes(current))$('country').value=current}}
function renderTop(rows){const top=rows.filter(x=>x.available&&x.speed_mbps_avg!=null).sort((a,b)=>b.speed_mbps_avg-a.speed_mbps_avg).slice(0,20);$('toplist').innerHTML=top.length?top.map((x,i)=>`<div class="topitem"><div class="rank">${i+1}</div><div><div class="topname">${esc(x.candidate)}</div><div class="hint">${esc(x.country||'--')} · ${x.tcp_ms??'--'} ms · ${x.exit_match==='same'?'真出口':'出口不同'}</div></div><div class="topspeed">${x.speed_mbps_avg}M</div></div>`).join(''):'<div class="hint">完成测速后自动按平均速度排名。</div>'}
function download(name,text,type='text/plain'){const b=new Blob([text],{type:type+';charset=utf-8'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),500)}async function copy(text){if(!text)return toast('当前没有可复制结果',true);await navigator.clipboard.writeText(text);toast('已复制到剪贴板')}
$('copyUsable').onclick=()=>copy((lastData?.results||[]).filter(x=>x.available).map(x=>x.candidate).join('\n'));$('copyVisible').onclick=()=>copy(filteredRows.map(x=>x.candidate).join('\n'));$('copyTop').onclick=()=>copy((lastData?.results||[]).filter(x=>x.speed_mbps_avg!=null).sort((a,b)=>b.speed_mbps_avg-a.speed_mbps_avg).slice(0,20).map(x=>x.candidate).join('\n'));$('txt').onclick=()=>download('proxyip-filtered.txt',filteredRows.map(x=>x.candidate).join('\n'));
$('csv').onclick=()=>{if(!filteredRows.length)return toast('没有可导出的结果',true);const fields=['candidate','available','generic_ok','tcp_ms','tls_ms','http_status','exit_ip','country','colo','exit_match','speed_mbps_avg','speed_mbps_min','speed_mbps_max','speed_success','error_stage','error'];const q=v=>'"'+String(v??'').replaceAll('"','""')+'"';download('proxyip-filtered.csv','\ufeff'+fields.join(',')+'\n'+filteredRows.map(r=>fields.map(f=>q(r[f])).join(',')).join('\n'),'text/csv')};
async function loadHistory(){if(!$('token').value.trim())return;try{const r=await fetch('/api/jobs',{headers:auth()});if(!r.ok)return;const d=await r.json(),jobs=d.jobs||[];$('history').innerHTML=jobs.length?jobs.map(j=>`<div class="history-item" data-job="${esc(j.id)}"><div class="history-top"><b>${esc(j.id)}</b><span>${esc(stateMap[j.state]||j.state)}</span></div><div class="history-sub">${new Date((j.created_at||0)*1000).toLocaleString()} · ${j.available||0}/${j.total||0} 可用 · ${j.high_speed||0} 高速</div></div>`).join(''):'<div class="hint">暂无历史任务。</div>';$('history').querySelectorAll('[data-job]').forEach(e=>e.onclick=()=>openJob(e.dataset.job))}catch(_){} }
async function openJob(id){currentJob=id;try{const r=await fetch('/api/jobs/'+id,{headers:auth()});const d=await r.json();if(!r.ok)throw new Error(d.detail||'读取失败');lastData=d;render(d);setRunning(!['done','cancelled'].includes(d.state));if(!['done','cancelled'].includes(d.state)){clearInterval(timer);timer=setInterval(poll,800)}toast('已载入历史任务 '+id)}catch(e){toast(e.message,true)}}$('refreshHistory').onclick=loadHistory;updateParse();loadHistory();
</script></body></html>'''
html_path.write_text(html, encoding='utf-8')

readme = readme_path.read_text(encoding='utf-8')
section = '''\n\n## 成熟扫描控制台\n\n前台首页 `/` 已升级为完整批量扫描控制台：批量导入/去重、快速/均衡/深度预设、双阶段实时进度、速率和 ETA、任务停止、最近任务恢复、地区/状态/速度筛选、100 行分页、TOP 20 高速节点、当前筛选 TXT/CSV 导出、复制可用节点，以及测速流量预估。\n\n测速采用“先筛选、后测速”策略。`speed.limit` 可限制仅对 TCP 延迟最优的前 N 个可用节点测速；0 表示全部可用节点。任务可通过 `POST /api/jobs/{job_id}/cancel` 请求停止，最近 30 个任务可通过 `GET /api/jobs` 查看。\n'''
if '## 成熟扫描控制台' not in readme:
    readme += section
readme_path.write_text(readme, encoding='utf-8')
