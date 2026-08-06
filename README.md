# 羽化面板 (yuhua-panel)

基于 [sillyGirl](https://github.com/smallfawn/sillyGirl) 的聊天机器人面板，兼容 AutMan 插件生态，支持 QQ / 微信 ClawBot / Telegram / Web / 钉钉 / QQ官方频道 多平台接入。

> 仅发布编译后的二进制与 Docker 运行时镜像，不含源码。

## 界面预览

![界面预览 1](https://gcore.jsdelivr.net/gh/lhz03/img@7387bc8c8d52ce15d22b5e99570ef795ac59abdc/2026/08/05/8e8e5231776721b9db197394aa424fba.png)

![界面预览 2](https://gcore.jsdelivr.net/gh/lhz03/img@f0a329b7c7bdb70180be4de70574ad1822b3f0d0/2026/08/05/7227dabbe023a7a35f40ab5c23f218a3.png)

## 快速开始

| 方式 | 平台 | 说明 |
|---|---|---|
| [Docker](#docker-部署推荐) | Linux | 一条命令部署，自动下载最新版 |
| [二进制](#二进制部署linux) | Linux | 直接运行 |
| [Windows](#windows-部署) | Windows | 解压即用 |

## Docker 部署（推荐）

镜像内置 Node 24 + Python 3.12 插件运行时，支持 **amd64 / arm64** 双架构，首次启动自动下载最新版主程序到宿主机 `/root/yuhua-panel/`。

### 国内服务器拉取镜像加速

Docker Hub 直连易断，先配置镜像加速器：

```bash
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": ["https://docker.1panel.live"]
}
EOF
systemctl restart docker
```

### 方式一：docker compose

创建 `docker-compose.yml`：

```yaml
services:
  yuhua-panel:
    image: yuhualhh/yuhua-panel:latest
    container_name: yuhua-panel
    restart: unless-stopped
    ports:
      - "6060:6060"
    environment:
      SILLYGIRL_DATA_PATH: /data
    volumes:
      - ${YUHUA_PANEL_DIR:-/root/yuhua-panel}:/app/main
      - ${YUHUA_PANEL_DIR:-/root/yuhua-panel}/data:/data
```

```bash
mkdir -p /root/yuhua-panel && cd /root/yuhua-panel
docker compose up -d
```

访问 `http://服务器IP:6060/admin`。

- 自定义目录：`YUHUA_PANEL_DIR=/自定义/路径 docker compose up -d`
- 更新：面板「更新」按钮或发「更新」，自动下载新版并重启

### 方式二：docker run

```bash
mkdir -p /root/yuhua-panel/data
docker run -d \
  --name yuhua-panel \
  --restart unless-stopped \
  -p 6060:6060 \
  -e SILLYGIRL_DATA_PATH=/data \
  -v /root/yuhua-panel:/app/main \
  -v /root/yuhua-panel/data:/data \
  yuhualhh/yuhua-panel:latest
```

## Linux二进制部署

下载 [Releases](https://github.com/yuhualhh/yuhua-panel/releases) 中 `yuhua-panel-linux-<arch>-<版本>.tar.gz`：

```bash
mkdir -p /opt/yuhua-panel && cd /opt/yuhua-panel
tar -xzf yuhua-panel-linux-amd64-*.tar.gz
chmod +x yuhua-panel
./yuhua-panel
```

数据存 `./data/`。

## Windows 部署

下载 [Releases](https://github.com/yuhualhh/yuhua-panel/releases) 中 `yuhua-panel-windows-amd64-<版本>.zip`，解压双击 `yuhua-panel.exe` 即可（数据存同目录 `data/`）。

## 自更新

- 启动时自动检查远程版本（每 5 分钟）
- 面板「更新」按钮 / 机器人发「更新」：在线更新并自动重启
- 机器人发「回退」：切换任意版本（旧版/当前/新版）
- Release 均带 `checksums.txt`，下载后校验 SHA256

## 接入适配器

- **QQ**：OneBot 反向 WebSocket，接入地址 `ws://<你的地址>:6060/qq/receive`（NapCat / Lagrange / go-cqhttp 兼容）
- **微信 ClawBot**：发「微信龙虾登录」扫码接入
- **Telegram**：面板配置 Bot Token
- **Web Bot**：内置轮询机器人，用户可在用户前台网页对话
- **钉钉**：面板配置 Client ID / Client Secret（Stream 模式，无需公网回调）
- **QQ 官方频道**：面板配置 AppID / Token / 密钥，支持 WebSocket 与 Webhook 两种接入方式

## 数据

全部数据在 `data/` 目录（`sillyGirl.db` + `plugins/`），备份/迁移直接拷贝整个 `data/`。

## 致谢

基于并延续 [cdle/sillyGirl](https://github.com/cdle/sillyGirl) 与 [smallfawn/sillyGirl](https://github.com/smallfawn/sillyGirl) 的项目思想与代码积累。

## 许可

MIT
