# 羽化面板 (yuhua-panel)

基于 [sillyGirl](https://github.com/smallfawn/sillyGirl) 的聊天机器人面板，完美适配兼容 AutMan 插件生态，无需改动插件直接放入即用，支持 QQ / 微信多ClawBot / 千寻微信Pro / 企业微信 AI Bot / Telegram / 钉钉 / QQ官方频道 / Web Bot 多平台接入

> 仅发布编译后的二进制与 Docker 镜像，不含源码

## 快速开始

| 方式 | 平台 | 说明 |
|---|---|---|
| [Docker](#docker-部署推荐) | Linux | 一条命令部署，自动下载最新版 |
| [二进制](#二进制部署linux) | Linux | 自配环境 Node 24 + Python 3.12 |
| [Windows](#windows-部署) | Windows | 自配环境 Node 24 + Python 3.12 |

## Docker 部署（推荐）

镜像内置 Node 24 + Python 3.12 插件运行环境，首次启动自动下载最新版主程序到宿主机 `/root/yuhua-panel/`

### 国内服务器拉取镜像加速

Docker Hub 直连易断，先配置镜像加速器：

```bash
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1panel.live",
    "https://dockerproxy.link"
  ]
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

访问 `http://服务器IP:6060/admin`

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

数据存 `./data/`

## Windows 部署

下载 [Releases](https://github.com/yuhualhh/yuhua-panel/releases) 中 `yuhua-panel-windows-amd64-<版本>.zip`，解压双击 `yuhua-panel.exe` 即可（数据存同目录 `data/`）

## 自更新

- 自动检查远程版本，管理员可发 `版本`检测新版
- 面板「更新」按钮 / 管理员可发「更新」：在线更新并自动重启
- 管理员可发「回退」：切换任意版本（旧版/当前/新版）
- Release 均带 `checksums.txt`，下载后校验 SHA256

## 接入适配器

- **QQ**：OneBot 反向 WebSocket，接入地址 `ws://<你的地址>:6060/qq/receive`（NapCat / LLBot / go-cqhttp 兼容）
- **微信 ClawBot**：用户发「微信龙虾登录」扫码接入聊天，管理员可发「微信龙虾管理」进行管理
- **千寻Pro**：PC 微信 hook 框架，在「框架设置-HTTP API服务端」页勾选「启用HTTPAPI、框架启动后自动开启HTTPAPI 」以及默认千寻监听接口7777，HTTP事件回调地址填 `http://<你的地址>:6060/qx/webhook`（可选 `webhook_key` 鉴权）；支持文本/图片/视频收发、好友自动同意、收款事件（10007/10015）
- **企业微信**：[点击查看配置教程](https://gcore.jsdelivr.net/gh/lhz03/img@b439d7ee31969c2102c08eba5f671e8fcb6f853f/2026/08/07/52d772bf84a495061e1ecf74c2347ba3.png)，企业微信群聊需@私聊不用，支持文本收发、markdown 图文/视频链接、进会话欢迎语
- **Telegram**：面板配置 Bot Token
- **钉钉**：面板配置钉钉 Stream 接入
- **QQ官方频道**：面板配置，支持 WebSocket / Webhook 双模式
- **Web**：内置轮询机器人，面板配置

## 数据

全部数据在 `data/` 目录（`sillyGirl.db` + `plugins/`），可备份/迁移直接拷贝整个 `data/`，另有管理员备份指令 `导出数据`

## 致谢

基于并延续 [cdle/sillyGirl](https://github.com/cdle/sillyGirl) 与 [smallfawn/sillyGirl](https://github.com/smallfawn/sillyGirl) 的项目思想与代码积累

## 许可

MIT
