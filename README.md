# Douyin Media Extractor (抖音媒体提取器)

`douyin_phaser.py` 是一个基于 Playwright 浏览器自动化的抖音媒体直链提取工具。支持提取： **视频 (4K)**、**图集** 和 **动图** 的直链提取。提供命令行工具 (CLI) 和 HTTP API 两种使用方式。

## ✨ 功能特点

- **全类型支持**: 视频 (`/video/`)、图文 (`/note/`)、动图 (`/note/` + GIF)
- **最高画质**: 自动选择 4K/2K/1080p 最高清晰度视频 + 原图质量封面
- **高清封面**: 智能选取封面，优先使用 CDN 无压缩 `/obj/` 链接
- **API 服务**: 内置 FastAPI 服务器，方便集成到其他系统
- **反爬虫绕过**: 基于 Playwright 模拟真实浏览器，自动处理签名和验证
- **短链智能识别**: 自动处理 `v.douyin.com` 短链，正确区分视频和图文内容

## ⚠️ 免责声明

1. 本项目仅供技术研究和学习交流使用，请勿用于非法用途。
2. 用户在使用本工具时，必须遵守当地法律法规。对于用户因非法使用而产生的任何法律纠纷，作者不承担任何责任。
3. 本工具仅提供解析功能，不存储任何视频资源。所有视频版权归原平台及作者所有。
4. 如果原平台认为本项目侵犯了您的权益，请联系我，我会立即处理。 📧


## 🚀 快速开始

### 方式一：Docker 快速部署 (仅媒体提取)

如果你只需要提取**单个视频/图文**的直链，无需任何配置，直接运行即可（不需要 Cookie）：

```bash
docker run -d -p 8000:8000 --name douyin-phaser ghcr.io/yusongxiao/douyin_phaser:main
```
服务启动后，访问 `http://localhost:8000` 即可使用。

### 方式二：Docker Compose 部署 (推荐 - 完整功能)

这种方式可以同时启动媒体提取 API (8000) 和用户主页提取 API (8001)，并且支持持久化 Cookie。

1. **生成 Cookie (必须)**
   
   由于容器内无法扫码登录，你需要先在宿主机生成 Cookie 文件：
   ```bash
   # 在项目目录下运行，会弹出浏览器让你扫码
   python douyin_user_phaser.py --login
   # 成功后会生成 douyin_cookies.json 文件
   ```

2. **启动服务**

   使用 Docker Compose 一键启动：
   ```bash
   docker compose up -d --build
   ```

   或者使用 Docker 命令直接运行 (如果你没有安装 Compose)：
   ```bash
   docker run -d \
     -p 8000:8000 \
     -p 8001:8001 \
     -v ${PWD}/douyin_cookies.json:/app/douyin_cookies.json \
     --name douyin-phaser \
     ghcr.io/yusongxiao/douyin_phaser:main \
     sh -c "uvicorn douyin_phaser_api:app --host 0.0.0.0 --port 8000 & uvicorn douyin_user_phaser_api:app --host 0.0.0.0 --port 8001 & wait"
   ```

### 方式三：源码部署

#### 1. 安装依赖

需要 Python 3.12+ 环境（与 `pyproject.toml`、Docker 保持一致）。

使用 uv 安装并运行：

```bash
uv sync
uv run playwright install chromium
uv run douyin_phaser_api.py       # 媒体接口，端口 8000
# 另开终端：
uv run douyin_user_phaser_api.py  # 用户作品接口，端口 8001
```

也可以使用 pip：

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装浏览器内核 (Playwright 需要)
playwright install chromium
```

#### 2. 启动 API 服务

启动 API 服务器，供其他程序调用：

```bash
python douyin_phaser_api.py
```
服务器默认运行在 `http://localhost:8000`。

**API 使用示例**:

```bash
# 提取视频/图文直链 (媒体提取 API)
curl "http://localhost:8000/?url=https://v.douyin.com/abc1234/"

# 提取用户主页所有作品 (用户提取 API)
curl "http://localhost:8001/?url=https://www.douyin.com/user/..."
```

**API 文档**:
浏览器访问 `http://localhost:8000/docs` (媒体提取) 或 `http://localhost:8001/docs` (用户提取) 查看完整的交互式 API 文档。

#### 3. 命令行使用 (CLI)

也可以直接运行脚本提取单个链接：

```bash
python douyin_phaser.py "https://v.douyin.com/abc1234/"
```

## 🛠️ API 返回结构

API 返回统一的 JSON 结构，方便调用方处理。

### 1. 媒体提取 API (端口 8000)

用于提取单个视频、图文或动图的直链。

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "title": "作品标题",
    "author": "作者昵称",
    "cover": "封面图URL",
    "type": "video | images",  // 顶层类型提示
    "items": [
      // 统一 Items 数组，只需遍历此数组即可
      {
        "type": "video",
        "video_url": "https://..."
      },
      {
        "type": "image",
        "image_url": "https://..."
      },
      {
        "type": "animated_image",
        "image_url": "https://...webp",
        "video_url": "https://...mp4"
      }
    ]
  }
}
```

### 2. 用户主页提取 API (端口 8001)

用于提取用户主页的所有作品链接。

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "nickname": "用户昵称",
      "sec_uid": "MS4wLjABAAAA...",
      "uid": "123456789",
      "avatar": "https://...",
      "signature": "用户签名",
      "aweme_count": 8
    },
    "works_count": 30,
    "works": [
      {
        "aweme_id": "7606955181091438309",
        "type": "note",
        "desc": "作品描述",
        "share_url": "https://www.douyin.com/note/7606955181091438309",
        "cover": "https://... (封面)",
        "create_time": 1771132277
      },
      {
        "aweme_id": "7599252551926900837",
        "type": "video",
        "desc": "作品描述",
        "share_url": "https://www.douyin.com/video/7599252551926900837",
        "cover": "https://... (封面)",
        "create_time": 1769338866
      }
    ]
  }
}
```

## 📚 更多文档

- [技术原理与架构详解](./原理.md)

