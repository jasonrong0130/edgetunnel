import asyncio
import csv
import io
import ipaddress
import json
import os
import re
import secrets
import ssl
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
STATIC_DIR = APP_DIR / "static"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("PROXY_TESTER_TOKEN", "").strip()
MAX_TARGETS = int(os.environ.get("MAX_TARGETS", "5000"))
DEFAULT_CHECK_CONCURRENCY = int(os.environ.get("CHECK_CONCURRENCY", "50"))
DEFAULT_SPEED_CONCURRENCY = int(os.environ.get("SPEED_CONCURRENCY", "4"))
DEFAULT_TIMEOUT = float(os.environ.get("PROBE_TIMEOUT", "7"))
DEFAULT_SPEED_BYTES = int(os.environ.get("SPEED_BYTES", str(5 * 1024 * 1024)))
DEFAULT_SPEED_REPEATS = int(os.environ.get("SPEED_REPEATS", "3"))

CF_TRACE_HOST = "www.cloudflare.com"
CF_TRACE_PATH = "/cdn-cgi/trace"
GENERIC_HOST = "www.gstatic.com"
GENERIC_PATH = "/generate_204"
SPEED_HOST = "speed.cloudflare.com"

TARGET_RE = re.compile(r"^[A-Za-z0-9._-]+$")
JOBS: Dict[str, dict] = {}

app = FastAPI(title="RN ProxyIP Tester", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def require_token(authorization: Optional[str], x_api_token: Optional[str]) -> None:
    if not TOKEN:
        raise HTTPException(status_code=503, detail="PROXY_TESTER_TOKEN is not configured")
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    elif x_api_token:
        supplied = x_api_token.strip()
    if not supplied or not secrets.compare_digest(supplied, TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")


def public_ip_ok(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return True
    return ip.is_global


def parse_target(raw: str) -> Tuple[str, int, str]:
    value = str(raw or "").strip()
    value = re.sub(r"^proxyip://", "", value, flags=re.I)
    if not value:
        raise ValueError("empty target")
    if any(ch.isspace() for ch in value) or "/" in value or "#" in value or "$" in value:
        raise ValueError("invalid characters")
    host = value
    port = 443
    if value.startswith("["):
        m = re.match(r"^\[([0-9A-Fa-f:]+)\](?::(\d+))?$", value)
        if not m:
            raise ValueError("invalid IPv6 target")
        host = m.group(1)
        if m.group(2):
            port = int(m.group(2))
    else:
        m = re.match(r"^([^:]+):(\d+)$", value)
        if m:
            host = m.group(1)
            port = int(m.group(2))
        elif value.count(":") > 1:
            host = value
    if not 1 <= port <= 65535:
        raise ValueError("port out of range")
    if not public_ip_ok(host):
        raise ValueError("private/reserved IPs are blocked")
    if ":" not in host and not TARGET_RE.match(host):
        raise ValueError("invalid hostname")
    normalized = "[{}]:{}".format(host, port) if ":" in host else "{}:{}".format(host, port)
    return host, port, normalized


async def hostname_is_public(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return public_ip_ok(host)
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None)
    ips = {info[4][0] for info in infos if info[4]}
    return bool(ips) and all(public_ip_ok(ip) for ip in ips)


async def close_writer(writer) -> None:
    if not writer:
        return
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def tcp_probe(host: str, port: int, timeout: float) -> dict:
    started = time.perf_counter()
    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        return {"ok": True, "ms": round((time.perf_counter() - started) * 1000, 1), "error": None}
    except Exception as exc:
        return {"ok": False, "ms": None, "error": str(exc)}
    finally:
        await close_writer(writer)


def parse_headers(header_bytes: bytes):
    text = header_bytes.decode("iso-8859-1", errors="replace")
    lines = text.split("\r\n")
    status = 0
    if lines:
        m = re.match(r"^HTTP/\d(?:\.\d)?\s+(\d{3})", lines[0])
        if m:
            status = int(m.group(1))
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status, headers


def decode_chunked(body: bytes) -> bytes:
    out = bytearray()
    pos = 0
    try:
        while pos < len(body):
            end = body.find(b"\r\n", pos)
            if end < 0:
                break
            size = int(body[pos:end].split(b";", 1)[0].strip(), 16)
            pos = end + 2
            if size == 0:
                break
            out.extend(body[pos:pos + size])
            pos += size + 2
        return bytes(out) if out else body
    except Exception:
        return body


async def https_via_proxy(proxy_host, proxy_port, sni_host, path, timeout, body_limit=1024 * 1024):
    context = ssl.create_default_context()
    writer = None
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy_host, proxy_port, ssl=context, server_hostname=sni_host),
            timeout=timeout,
        )
        tls_ms = round((time.perf_counter() - started) * 1000, 1)
        request = (
            "GET {} HTTP/1.1\r\nHost: {}\r\nUser-Agent: RN-ProxyIP-Tester/0.1\r\n"
            "Accept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"
        ).format(path, sni_host).encode("ascii")
        writer.write(request)
        await asyncio.wait_for(writer.drain(), timeout=timeout)

        raw = bytearray()
        cap = body_limit + 64 * 1024
        while len(raw) < cap:
            chunk = await asyncio.wait_for(reader.read(min(64 * 1024, cap - len(raw))), timeout=timeout)
            if not chunk:
                break
            raw.extend(chunk)

        split = bytes(raw).find(b"\r\n\r\n")
        if split < 0:
            return {"ok": False, "tls_ms": tls_ms, "status": None, "body": b"", "error": "invalid HTTP response"}
        status, headers = parse_headers(bytes(raw[:split]))
        body = bytes(raw[split + 4:])
        if headers.get("transfer-encoding", "").lower() == "chunked":
            body = decode_chunked(body)
        return {
            "ok": 100 <= status <= 599,
            "tls_ms": tls_ms,
            "status": status or None,
            "body": body[:body_limit],
            "error": None if status else "missing HTTP status",
        }
    except Exception as exc:
        return {"ok": False, "tls_ms": None, "status": None, "body": b"", "error": str(exc)}
    finally:
        await close_writer(writer)


def parse_trace(body: bytes) -> dict:
    data = {}
    for line in body.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


async def speed_test(proxy_host, proxy_port, size_bytes, timeout):
    context = ssl.create_default_context()
    writer = None
    path = "/__down?bytes={}".format(size_bytes)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy_host, proxy_port, ssl=context, server_hostname=SPEED_HOST),
            timeout=timeout,
        )
        request = (
            "GET {} HTTP/1.1\r\nHost: {}\r\nUser-Agent: RN-ProxyIP-Tester/0.1\r\n"
            "Accept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"
        ).format(path, SPEED_HOST).encode("ascii")
        writer.write(request)
        await asyncio.wait_for(writer.drain(), timeout=timeout)
        header_bytes = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=timeout)
        status, _ = parse_headers(header_bytes[:-4])
        if status < 200 or status >= 400:
            return {"ok": False, "status": status, "mbps": None, "bytes": 0, "seconds": None, "error": "HTTP {}".format(status)}
        received = 0
        body_started = time.perf_counter()
        while received < size_bytes:
            chunk = await asyncio.wait_for(reader.read(min(64 * 1024, size_bytes - received)), timeout=timeout)
            if not chunk:
                break
            received += len(chunk)
        elapsed = max(time.perf_counter() - body_started, 0.001)
        ok = received >= min(size_bytes, 128 * 1024)
        return {
            "ok": ok,
            "status": status,
            "mbps": round(received * 8 / elapsed / 1_000_000, 2) if ok else None,
            "bytes": received,
            "seconds": round(elapsed, 3),
            "error": None if ok else "short download",
        }
    except Exception as exc:
        return {"ok": False, "status": None, "mbps": None, "bytes": 0, "seconds": None, "error": str(exc)}
    finally:
        await close_writer(writer)


def classify_exit(candidate_host, exit_ip):
    if not exit_ip:
        return "unknown"
    try:
        return "same" if str(ipaddress.ip_address(candidate_host)) == str(ipaddress.ip_address(exit_ip)) else "different"
    except ValueError:
        return "unknown"


async def test_one(raw, generic_test, timeout):
    started = time.time()
    try:
        host, port, normalized = parse_target(raw)
        if not await hostname_is_public(host):
            raise ValueError("hostname resolves to private/reserved address")
    except Exception as exc:
        return {"input": raw, "candidate": raw, "available": False, "generic_ok": False, "error_stage": "input", "error": str(exc), "tested_at": started}

    tcp = await tcp_probe(host, port, timeout)
    if not tcp["ok"]:
        return {
            "input": raw, "candidate": normalized, "host": host, "port": port,
            "available": False, "generic_ok": False, "tcp_ms": None, "tls_ms": None,
            "http_status": None, "exit_ip": None, "country": None, "colo": None,
            "exit_match": "unknown", "error_stage": "tcp", "error": tcp["error"], "tested_at": started,
        }

    trace = await https_via_proxy(host, port, CF_TRACE_HOST, CF_TRACE_PATH, timeout, 128 * 1024)
    if not trace["ok"]:
        return {
            "input": raw, "candidate": normalized, "host": host, "port": port,
            "available": False, "generic_ok": False, "tcp_ms": tcp["ms"], "tls_ms": trace["tls_ms"],
            "http_status": trace["status"], "exit_ip": None, "country": None, "colo": None,
            "exit_match": "unknown", "error_stage": "tls_http",
            "error": trace["error"] or "Cloudflare trace failed", "tested_at": started,
        }

    trace_data = parse_trace(trace["body"])
    exit_ip = trace_data.get("ip")
    generic_ok = None
    generic_status = None
    generic_error = None
    if generic_test:
        generic = await https_via_proxy(host, port, GENERIC_HOST, GENERIC_PATH, timeout, 64 * 1024)
        generic_status = generic["status"]
        generic_ok = bool(generic["ok"] and generic["status"] in (200, 204, 301, 302, 403, 404))
        generic_error = generic["error"]

    return {
        "input": raw, "candidate": normalized, "host": host, "port": port,
        "available": True, "generic_ok": generic_ok, "generic_status": generic_status,
        "generic_error": generic_error, "tcp_ms": tcp["ms"], "tls_ms": trace["tls_ms"],
        "http_status": trace["status"], "exit_ip": exit_ip, "country": trace_data.get("loc"),
        "colo": trace_data.get("colo"), "exit_match": classify_exit(host, exit_ip),
        "error_stage": None, "error": None, "tested_at": started,
    }


async def run_job(job):
    targets = job["targets"]
    settings = job["settings"]
    check_sem = asyncio.Semaphore(settings["check_concurrency"])
    job["results"] = [
        {"input": raw, "candidate": raw, "available": None, "state": "pending"}
        for raw in targets
    ]
    index_by_target = {raw: idx for idx, raw in enumerate(targets)}

    async def wrapped_check(raw):
        async with check_sem:
            idx = index_by_target[raw]
            job["results"][idx]["state"] = "checking"
            result = await test_one(raw, settings["generic_test"], settings["timeout"])
            result["state"] = "checked"
            job["results"][idx] = result
            job["completed"] += 1
            if result.get("available"):
                job["available"] += 1
            if result.get("exit_match") == "same":
                job["same_exit"] += 1

    job["state"] = "checking"
    await asyncio.gather(*(wrapped_check(raw) for raw in targets))
    ordered = job["results"]

    speed_cfg = settings["speed"]
    if speed_cfg["enabled"]:
        speed_targets = [r for r in ordered if r.get("available")]
        job["speed_total"] = len(speed_targets)
        job["state"] = "speeding"
        speed_sem = asyncio.Semaphore(speed_cfg["concurrency"])

        async def wrapped_speed(result):
            async with speed_sem:
                runs = []
                for _ in range(speed_cfg["repeats"]):
                    runs.append(await speed_test(result["host"], result["port"], speed_cfg["bytes"], max(settings["timeout"], 15.0)))
                good = [r["mbps"] for r in runs if r.get("ok") and isinstance(r.get("mbps"), (int, float))]
                result["speed_runs"] = runs
                result["speed_success"] = len(good)
                result["speed_mbps_avg"] = round(sum(good) / len(good), 2) if good else None
                result["speed_mbps_min"] = round(min(good), 2) if good else None
                result["speed_mbps_max"] = round(max(good), 2) if good else None
                job["speed_completed"] += 1

        await asyncio.gather(*(wrapped_speed(r) for r in speed_targets))

    job["state"] = "done"
    job["finished_at"] = time.time()
    persist_job(job)


def persist_job(job):
    path = DATA_DIR / "{}.json".format(job["id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_job(job_id):
    if job_id in JOBS:
        return JOBS[job_id]
    path = DATA_DIR / "{}.json".format(job_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def sanitize_targets(payload) -> List[str]:
    raw = payload.get("targets", "")
    items = [str(x).strip() for x in raw] if isinstance(raw, list) else re.split(r"[\r\n,\s]+", str(raw))
    out, seen = [], set()
    for item in items:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) > MAX_TARGETS:
            raise HTTPException(status_code=400, detail="too many targets; max {}".format(MAX_TARGETS))
    if not out:
        raise HTTPException(status_code=400, detail="no targets")
    return out


def clamp_int(value, default, low, high):
    try:
        n = int(value)
    except Exception:
        n = default
    return max(low, min(high, n))


def clamp_float(value, default, low, high):
    try:
        n = float(value)
    except Exception:
        n = default
    return max(low, min(high, n))


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    return {"ok": True, "jobs": len(JOBS), "token_configured": bool(TOKEN)}


@app.post("/api/jobs")
async def create_job(request: Request, authorization: Optional[str] = Header(None), x_api_token: Optional[str] = Header(None)):
    require_token(authorization, x_api_token)
    payload = await request.json()
    targets = sanitize_targets(payload)
    speed = payload.get("speed") or {}
    settings = {
        "check_concurrency": clamp_int(payload.get("check_concurrency"), DEFAULT_CHECK_CONCURRENCY, 1, 200),
        "generic_test": bool(payload.get("generic_test", True)),
        "timeout": clamp_float(payload.get("timeout"), DEFAULT_TIMEOUT, 2.0, 20.0),
        "speed": {
            "enabled": bool(speed.get("enabled", True)),
            "concurrency": clamp_int(speed.get("concurrency"), DEFAULT_SPEED_CONCURRENCY, 1, 10),
            "bytes": clamp_int(speed.get("bytes"), DEFAULT_SPEED_BYTES, 1024 * 1024, 50 * 1024 * 1024),
            "repeats": clamp_int(speed.get("repeats"), DEFAULT_SPEED_REPEATS, 1, 5),
        },
    }
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "state": "queued", "created_at": time.time(), "finished_at": None,
        "total": len(targets), "completed": 0, "available": 0, "same_exit": 0,
        "speed_total": 0, "speed_completed": 0, "settings": settings,
        "targets": targets, "results": [],
    }
    JOBS[job_id] = job
    asyncio.create_task(run_job(job))
    return {"id": job_id, "state": job["state"], "total": job["total"]}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, authorization: Optional[str] = Header(None), x_api_token: Optional[str] = Header(None)):
    require_token(authorization, x_api_token)
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/jobs/{job_id}/export.csv")
async def export_csv(job_id: str, authorization: Optional[str] = Header(None), x_api_token: Optional[str] = Header(None)):
    require_token(authorization, x_api_token)
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    buf = io.StringIO()
    fields = [
        "candidate", "available", "generic_ok", "tcp_ms", "tls_ms", "http_status",
        "exit_ip", "country", "colo", "exit_match", "speed_mbps_avg", "speed_mbps_min",
        "speed_mbps_max", "speed_success", "error_stage", "error",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in job.get("results", []):
        writer.writerow(row)
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="proxyip-{}.csv"'.format(job_id)},
    )
