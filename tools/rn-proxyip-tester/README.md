# RN ProxyIP Tester

给普通 Linux VPS（例如 RackNerd）使用的 ProxyIP 批量检测 + 出口验证 + 二阶段测速工具。

## 为什么放到 RN

Cloudflare Worker 内部直接 `connect()` 某些可用 ProxyIP 时可能返回 `TCP Loop detected`。RN 是普通公网 VPS，可以从真实外部网络发起：

`RN -> ProxyIP:443 -> SNI目标 -> Internet`

因此测试结果更接近实际客户端链路。

## V0.1 功能

- 批量粘贴 IP / 域名 / `host:port`
- 默认 50 并发做快速筛选
- 默认拒绝私网、保留、回环地址
- 第一阶段：
  - TCP 可达
  - TLS/SNI
  - `www.cloudflare.com/cdn-cgi/trace`
  - 读取真实出口 IP、国家代码、Cloudflare colo
  - 可选 `www.gstatic.com/generate_204` 通用 SNI 测试
- 第二阶段：
  - 只对第一阶段可用的 ProxyIP 测速
  - 默认 5 MiB × 3 次
  - 默认测速并发 4
  - 平均 / 最低 / 最高 Mbps
- 判断入口 IP 与真实出口 IP 是否一致
- 实时进度
- CSV 导出
- 已完成任务写入 `data/<job-id>.json`
- API Token 鉴权

## 部署

```bash
git clone -b feature/rn-proxyip-tester https://github.com/jasonrong0130/edgetunnel.git
cd edgetunnel/tools/rn-proxyip-tester
sudo bash install.sh
```

安装后默认只监听 `127.0.0.1:8788`。先用 SSH 隧道访问：

```bash
ssh -L 8788:127.0.0.1:8788 root@你的RN
```

浏览器打开：

```text
http://127.0.0.1:8788
```

Token：

```bash
sudo grep PROXY_TESTER_TOKEN /etc/rn-proxyip-tester.env
```

## 测速说明

测速走：

`RN -> ProxyIP -> speed.cloudflare.com`

请求 `speed.cloudflare.com/__down?bytes=...`，测的是 ProxyIP 的实际 HTTPS/SNI 中转吞吐，不是 ping。

推荐：
- 快速筛选并发：50
- 测速并发：3~5
- 快速测速：5 MiB × 3
- 深度测速：30 MiB × 3，只对排名靠前的少量节点

不要把 50 个节点同时做大文件测速，否则 RN 自己的带宽会成为瓶颈。

## 结果字段

- `available`: Cloudflare SNI/TLS/HTTP 链路可用
- `generic_ok`: gstatic 通用 HTTPS/SNI 是否可用
- `exit_ip`: Cloudflare trace 看到的真实出口
- `exit_match`: `same` / `different` / `unknown`
- `speed_mbps_avg/min/max`: 二阶段测速
- `tcp_ms`: TCP 建连延迟
- `tls_ms`: TLS 连接建立耗时

## 安全

默认：
- 只监听 `127.0.0.1`
- API 强制 Token
- 拒绝非公网 IP
- 单任务最多 5000 个目标
- 快速检测并发最高 200
- 测速并发最高 10
- 单次测速最大 50 MiB

以后接 EDT2 时，建议用 Caddy 给 RN 单独开 HTTPS 域名，并继续保留独立 API Token。


## 成熟扫描控制台

前台首页 `/` 已升级为完整批量扫描控制台：批量导入/去重、快速/均衡/深度预设、双阶段实时进度、速率和 ETA、任务停止、最近任务恢复、地区/状态/速度筛选、100 行分页、TOP 20 高速节点、当前筛选 TXT/CSV 导出、复制可用节点，以及测速流量预估。

测速采用“先筛选、后测速”策略。`speed.limit` 可限制仅对 TCP 延迟最优的前 N 个可用节点测速；0 表示全部可用节点。任务可通过 `POST /api/jobs/{job_id}/cancel` 请求停止，最近 30 个任务可通过 `GET /api/jobs` 查看。
