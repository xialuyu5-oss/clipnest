# ClipNest · 留住喜欢的视频

**网站先检查环境 · v1.4.0-alpha.2：**进入网站后自动检测本机，环境齐全就进入完整下载界面；缺少组件时才提示对应软件和补装入口。Windows 按需安装且逐项确认；Android 新增系统分享链接接收。解析、视频传输和合并都在用户设备完成。

[网站入口](https://xialuyu5-oss.github.io/clipnest/) · [新版说明](docs/releases/v1.4.0-alpha.2.md) · [本机安装说明](docs/LOCAL_PROCESSING.md)

**当前源码更新（2026-09-20）：**新增九个平台接入、19 个官网图标，以及本机 VPN 代理启动选项。使用这些改动可运行当前源码或当前网站部署生成的 PC 包；现有 alpha.2 Release 附件仍是此前构建。[更新记录](CHANGELOG.md) · [本机代理设置](docs/LOCAL_PROCESSING.md#using-an-existing-local-vpn-proxy)

首次使用需要安装并启动本机组件。检测就绪后，当前标签会切换到 `127.0.0.1:8000` 的完整界面；使用期间保持组件运行。网站不提供视频中转处理服务。小程序仍最后处理。

**粘贴链接，选择清晰度，确认后下载。**

ClipNest 是一个开源视频下载项目，包含自托管 Web 版、在手机内运行引擎的 Android 版，以及早期微信小程序。各版本的能力和完成程度不同，下面分别说明。

[English](README.md) · [需求演进](docs/REQUIREMENTS.md) · [安装说明](docs/WEB_INSTALL.md) · [验证记录](docs/TESTING.md)

[**在线交互预览**](https://xialuyu5-oss.github.io/clipnest/preview/?lang=zh-CN) · [12 种语言的项目介绍](docs/i18n/zh-CN.md)

[English](README.md) · 简体中文 · [繁體中文](docs/i18n/zh-TW.md) · [日本語](docs/i18n/ja.md) · [한국어](docs/i18n/ko.md) · [Español](docs/i18n/es.md) · [Français](docs/i18n/fr.md) · [Deutsch](docs/i18n/de.md) · [Português](docs/i18n/pt.md) · [Русский](docs/i18n/ru.md) · [العربية](docs/i18n/ar.md) · [हिन्दी](docs/i18n/hi.md)

**本项目代码由 OpenAI Vibe Coding 开发，使用 OpenAI ChatGPT 和 Codex。** 用户提出目标、审阅体验并决定修改方向；AI 生成和修订代码、文档，并通过工具辅助测试。这是独立项目，不代表 OpenAI 官方产品、认证或背书。

![ClipNest Web 原创演示与清晰度选择](docs/images/desktop-20260920.png)

*2026-09-20 当前源码的真实界面截图。使用项目原创演示素材，不代表真实平台下载验收。在线预览无需安装，仅提供这一原创素材的操作演示。*

<details>
<summary>19 个平台与官网图标</summary>

![ClipNest 平台列表](docs/images/platforms-20260920.png)

接入解析器不等于所有当前链接均可用，详见[验证范围与限制](docs/PLATFORMS.md)。

</details>

## 先选版本

| 版本 | 在哪里解析和下载 | 当前能力 | 当前交付 |
| --- | --- | --- | --- |
| **Web v1.3.1** | 自己的电脑或自建服务器 | 平台链接解析、清晰度选择、下载合并、暂停续传、浏览器保存 | ZIP / tar.gz 部署包；需要 Python、FFmpeg 和适用的 JS 运行环境 |
| **Android v1.4.0-alpha.2** | 手机本机 | 内置解析／下载／合并引擎、持久任务、系统文件导出 | 源码及构建说明；本地开发 APK 已通过模拟器测试。原生依赖对应源码与许可告知补齐前，暂不公开附加 APK |
| **微信小程序 v1.4.0-alpha.1** | 手机内的小程序 | HTTPS MP4 直链信息读取、下载、来源支持时续传、保存相册 | 可导入的开发工程 ZIP；未发布到微信，平台分享页解析尚未实现 |
| **iOS** | 计划为手机本机 | 已准备可复用界面、数据模型及原生消息协议 | 本轮暂缓，没有 iOS App、IPA 或上架入口 |

[Web 版本说明](docs/releases/v1.3.0.md) · [移动预览说明](docs/releases/v1.4.0-alpha.1.md) · [Android 构建](clients/android/README.md) · [小程序使用](clients/wechat/README.md)

## 使用流程与主要功能

1. **粘贴链接并选择实际格式。** 展示来源可用的清晰度、帧率、编码、音轨状态和已知／估算大小。取不到的信息保留未知，不编造。
2. **每次下载先确认。** 查看视频时长、预计大小和参考下载时间，由用户决定开始。应用不设置固定视频大小、时长或总下载时间上限。
3. **查看进度和剩余时间。** 显示进度、速度和 ETA；Android 标明当前轨道估计，Web 区分整体与当前轨道，未知时不显示虚假倒计时。
4. **随时暂停或取消。** 暂停保留进度，源站支持时续传；取消先停止工作进程，再删除缓存。合并阶段可取消，不支持暂停。
5. **保存成品。** Web 和 Android 按需合并分离音视频轨道，默认不转码。完成文件和检查点保留到用户删除，不再定时失效；已导出的文件不随任务删除。

实际存储空间、源站行为和手机运行环境仍会影响下载。下载前耗时采用明确标注的 **1–10 MB/s 参考速度**，不是实测网速，也不承诺完成时间。[下载原理 →](docs/ARCHITECTURE.md)

当前 Web 和 Android 源码接入 **YouTube、X / Twitter、TikTok、Instagram、Facebook、Vimeo、Bilibili、Dailymotion、Reddit、Twitch、抖音、小红书、微博、西瓜视频、AcFun、新片场、TED、Pinterest、Niconico** 的 yt-dlp 解析器。接入不等于每条链接已验证可用；来源权限、地区、风控、接口变化和 DRM 均可能影响结果。TikTok 与抖音分别处理。小程序当前仅接受 MP4 直链。[链接范围、验证记录和限制](docs/PLATFORMS.md)。

Web 另有本机 B站扫码登录和深浅主题；真实会员高清下载尚未完成验收，其他平台及 Android 的会员登录未实现。

## 从网站开始使用

1. 打开[网站入口](https://xialuyu5-oss.github.io/clipnest/)，自动检查本机环境。
2. 首次使用时下载、解压 PC 包，运行 `install-missing.bat`，确认补齐缺项。
3. 运行 `start-local.bat`，返回网站重新检测，就绪后自动打开完整界面。
4. 使用期间保持本机组件运行；浏览器询问本机连接权限时由你确认。

无法连接只表示尚未检测，不等于没有安装 Python 或 FFmpeg。详见[本机安装说明](docs/LOCAL_PROCESSING.md)。

## 直接启动 Web 版

先安装 **Python 3.11+、FFmpeg（包含 ffprobe）**，以及 YouTube 所需的 **Deno 2.3+ 或 Node.js 22+**，确保系统能找到这些工具。解压 Web 部署包或源码后运行：

```sh
python start.py
```

Windows 可双击 `start.bat`；macOS/Linux 使用 `python3 start.py` 或 `bash start.sh`。启动器创建项目自己的虚拟环境，首次联网安装 Python 依赖，然后打开 **http://127.0.0.1:8000**。使用网页时保持服务运行。系统运行环境需要单独安装。

```sh
python start.py --port 8001
python start.py --update
```

个人本机使用无需 `.env`；需要改配置时才复制 `.env.example` 为 `.env`，不要提交真实配置。局域网、公网访问和会员模式请按[安装说明](docs/WEB_INSTALL.md)、[部署与排障](docs/DEPLOYMENT.md)配置。

Dockerfile 和 Compose 已提供，但尚未验证镜像构建运行。公开 GitHub 源码不等于已经部署在线网站；离线界面预览也不能解析真实链接。

## 多语言与手机布局

首次打开默认英文。可选择 **English、简体中文、繁體中文、日本語、한국어、Español、Français、Deutsch、Português、Русский、العربية、हिन्दी**，记忆选择，支持阿拉伯语右到左布局。视频原始标题保留原文。控件保留最小触控尺寸，窄窗口允许换行。

<details>
<summary>手机网页与独立 Android 预览截图</summary>

<img src="docs/images/mobile-20260920.png" alt="手机网页的原创演示格式选择" width="320">
<img src="docs/images/android.png" alt="Android 16 模拟器中实际运行的独立应用" width="320">

前图是响应式 Web，后图是独立 Android 应用。尚无微信小程序或 iOS 的实机截图。

</details>

## 从原始需求到当前功能

| 用户需求／反馈 | 实现变化 |
| --- | --- |
| 做一个能解析 X、YouTube、TikTok 等链接，并选择清晰度下载的网站 | Web 解析及真实格式选择 |
| 不要固定临时文件大小上限，由用户确认 | 每次下载确认，移除固定文件、临时空间、时长和总耗时上限 |
| 帧率和音频编码不要无故显示未知 | 音轨区分有／无／未知，Web 尽力取样补全缺失元信息 |
| 默认英文，可选主流语言 | 12 语言、选择记忆、阿拉伯语 RTL |
| 控件太挤；显示剩余时间；支持暂停续传和取消清缓存 | 最小控件尺寸、ETA 和下载过程控制 |
| 去掉 60 分钟保留与重启失效 | 任务和文件持久化，未完成任务重启后暂停等待继续 |
| 新增手机独立运行版本，考虑 iOS 共通性 | Android 端侧引擎、共通模块和有限的纯端侧小程序；iOS 暂缓 |

固定限制和定时清理是早期实现选择，**不是用户原始要求**。小程序分享页解析和分轨合并仍属未完成项，不能写成用户已同意放弃。[完整需求与变更记录 →](docs/REQUIREMENTS.md)

## 已验证与未验证

- **Web：**226 项 Python 回归测试（含环境检测、平台路由与本机代理）、前端及多语言检查；真实本地 HTTP/HLS 续传；响应式浏览器流程；此前 Windows 解压部署包启动。当前源码已通过显式本机代理，从真实网页接口取得一个公开 X 样本的格式列表。
- **Android：**ARM64/x86_64 构建、APK 签名校验、Android 16 x86_64 模拟器 4 项集成测试，包含安装包内 yt-dlp 下载本地 HTTP 素材及 FFmpeg 合并后的音画检查。
- **共通／小程序：**12 语言、真实 MP4 素材元信息、HTTP Range 续传和字节一致性、来源变化拒绝及取消清理。微信原生下载退路和相册调用仍使用适配器测试。

**尚未验证：**全部平台当前实链、真实会员高清、Android 真机／后台／大文件行为、微信开发者工具与真机、Docker、macOS、公网部署。模拟器和测试素材不能证明这些场景。Android 安装包公开分发前，还需补齐匹配的原生依赖源码与许可告知。[测试复现](docs/TESTING.md) · [移动端待办](docs/MOBILE_TARGETS.md)

## 源码、成品与许可

源码保留功能实现、可编辑语言资源、测试维护工具、原始需求及变化、环境配置说明和截图。生成的部署包与安装包属于 Release；真实配置、用户媒体、凭据、签名密钥、开发缓存和运行日志不进入仓库。[源码结构与构建约定](docs/RELEASING.md)

Web、可独立复用的界面／共通模块及小程序采用 **[MIT](LICENSE)**；Android 应用采用 **[GPL-3.0-only](clients/android/LICENSE)**；原创演示素材采用 **[CC0 1.0](docs/ASSETS.md)**。第三方依赖保留各自许可，详见 [Android 依赖与分发状态](clients/android/THIRD_PARTY_NOTICES.md)。

仅处理自己拥有或获准下载的内容。本项目不解除 DRM，不授予来源视频权利；平台名称不代表合作、认证或背书。
