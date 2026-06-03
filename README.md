# Polymarket Copy Trader

Polymarket 跟单机器人 — 监控目标钱包交易，通过 `pm-trader` CLI 模拟跟单，提供实时盈亏仪表盘。

**技术栈**: FastAPI + SQLite + Vue 3 CDN + pm-trader (paper trading)

## 架构

```
Polymarket Data API ──→ scanner.py ──→ pm-trader CLI (paper trading)
                              │
                              ├── SQLite (trade_log, pnl_snapshots, wallets)
                              └── FastAPI :8766 ──→ Vue 3 SPA Dashboard
```

## 本地开发

```bash
# 安装依赖
pip install fastapi uvicorn[standard] polymarket-paper-trader

# 启动服务 (http://localhost:8766)
python main.py

# 环境变量
SCAN_INTERVAL=120    # 扫描间隔(秒)，默认120
SCAN_ENABLED=0       # 设为0禁用扫描(仅API)
DB_PATH=data/trade.db
```

## NAS 部署 (极空间 Z2Pro / ARM64)

### 前置条件

- 极空间已启用 SSH（系统设置 → 高级 → SSH）
- 已安装 Docker

### 首次部署

```bash
# 1. SSH 登录极空间
ssh your-nas-ip -p 2222

# 2. 拉取镜像 (多平台: amd64 + arm64)
sudo docker pull mao968/poly-trade:latest

# 3. 创建数据卷 (持久化)
sudo docker volume create poly-trade-data

# 4. 启动容器
sudo docker run -d \
  --name polymarket-copy-trader \
  --restart unless-stopped \
  -p 8766:8766 \
  -v poly-trade-data:/app/data \
  -e TZ=Asia/Shanghai \
  -e PYTHONUNBUFFERED=1 \
  -e SCAN_INTERVAL=120 \
  mao968/poly-trade:latest

# 5. 检查运行状态
sudo docker logs -f polymarket-copy-trader
```

### 更新部署

```bash
sudo docker pull mao968/poly-trade:latest
sudo docker stop polymarket-copy-trader
sudo docker rm polymarket-copy-trader
sudo docker run -d \
  --name polymarket-copy-trader \
  --restart unless-stopped \
  -p 8766:8766 \
  -v poly-trade-data:/app/data \
  -e TZ=Asia/Shanghai \
  -e PYTHONUNBUFFERED=1 \
  -e SCAN_INTERVAL=120 \
  mao968/poly-trade:latest
```

### 资源限制 (可选)

```bash
  --cpus 1 \
  --memory 512m \
```

### 常用命令

```bash
# 查看日志
sudo docker logs -f polymarket-copy-trader

# 查看最近30行日志
sudo docker logs --tail 30 polymarket-copy-trader

# 停止容器
sudo docker stop polymarket-copy-trader

# 重启容器
sudo docker restart polymarket-copy-trader

# 进入容器调试
sudo docker exec -it polymarket-copy-trader bash

# 查看数据文件
sudo docker exec polymarket-copy-trader ls -la /app/data/

# 查看数据库内容
sudo docker exec polymarket-copy-trader sqlite3 /app/data/trade.db ".tables"
```

## Dashboard

启动后访问 `http://<nas-ip>:8766`

三个标签页：
- **📊 监控面板** — 实时盈亏、交易明细、持仓追踪
- **🔍 钱包管理** — 添加/移除跟单钱包、搜索候选钱包
- **📈 分析** — 成功率、对比图表、回测、组合分析

## CI/CD (GitHub Actions)

推送 `master` 分支自动触发构建，推送到 Docker Hub `mao968/poly-trade:latest`。

构建目标: `linux/amd64` + `linux/arm64`

```yaml
# 手动触发: GitHub → Actions → Build and Push → Run workflow
# 或推送代码自动触发
git push origin master
```

### 配置 Secrets

GitHub → Settings → Secrets and variables → Actions：

| Secret | 说明 |
|--------|------|
| `DOCKER_USERNAME` | Docker Hub 用户名 |
| `DOCKER_TOKEN` | Docker Hub Access Token |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SCAN_INTERVAL` | `120` | 钱包扫描间隔(秒) |
| `SCAN_ENABLED` | `1` | 设为 `0` 禁用交易扫描 |
| `DB_PATH` | `data/trade.db` | SQLite 数据库路径 |
| `TZ` | `UTC` | 时区 (建议 `Asia/Shanghai`) |
| `PYTHONUNBUFFERED` | `0` | 设为 `1` 实时输出日志 |

## 数据持久化

Docker 数据卷 `poly-trade-data` 挂载到容器内 `/app/data`：

- `trade.db` — SQLite 数据库 (钱包、交易记录、盈亏快照)
- pm-trader 账户状态在每个容器内独立

**注意**: 重建容器时 `pm-trader` 的模拟账户会被重置为 $500 初始资金，但交易历史和钱包配置保留在数据卷中。

## 项目结构

```
├── main.py              # FastAPI 入口
├── scanner.py           # 交易扫描 + 跟单执行
├── trader.py            # pm-trader CLI 封装
├── database.py          # SQLite schema + 迁移
├── config.py            # 配置常量
├── models.py            # Pydantic 模型
├── websocket.py         # WebSocket 管理
├── alerts.py            # 告警逻辑
├── scores.py            # 钱包评分
├── backtest.py          # 历史回测
├── api/
│   ├── state.py         # 状态快照 + 行情历史
│   ├── wallets.py       # 钱包 CRUD + 持仓
│   ├── trades.py        # 交易查询
│   ├── summary.py       # 汇总统计 + 成功率
│   ├── backtest.py      # 回测 API
│   └── portfolio.py     # 组合分析
├── static/              # Vue 3 前端 (CDN, 无构建)
│   ├── index.html
│   ├── app.js
│   └── components/
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/docker-build.yml
```
