# 流光璃韵 · Android 版

把原桌面端 `app/core/*` 复用，UI 用 Kivy/Material Design 重写。**无需本地装 Android 工具链**，推到 GitHub 即可云端编译。

## 项目结构

```
kivy_app/
├── main.py                    # Kivy 入口
├── buildozer.spec             # Android 打包配置
├── requirements.txt
├── .github/workflows/build-apk.yml    # 云端编译 (GitHub Actions)
├── app/
│   ├── app.py                 # Kivy App
│   ├── config.py              # 复用
│   ├── core/                  # 复用桌面端 (跨平台适配)
│   │   ├── tools.py           # 22 工具定义
│   │   ├── ffmpeg.py          # 跨平台 FFmpeg 探测
│   │   ├── ffmpeg_bootstrap.py# Android 首次自动下载 ffmpeg
│   │   ├── tts.py             # Edge-TTS
│   │   ├── worker.py          # FFmpegWorker
│   │   └── m3u8.py
│   └── ui/
│       ├── main_screen.py     # 主屏 (12 工具卡片)
│       ├── tool_screen.py     # 工具屏
│       ├── widgets.py         # 自定义控件
│       ├── theming.py         # 国风配色
│       └── registry.py        # 工具注册表
└── assets/
    ├── icon.png
    └── presplash.png
```

## 编译流程（用户只需 3 步）

### 步骤 1：推到 GitHub

```bash
cd kivy_app
git init
git add .
git commit -m "init: 流光璃韵 Android 版"
git branch -M main
git remote add origin https://github.com/<你的用户名>/liuguangliyun.git
git push -u origin main
```

### 步骤 2：触发云端编译

**自动触发**：push 到 `main` 分支后自动开始编译。

**手动触发**：
1. 打开 GitHub 仓库页面
2. 点 **Actions** 标签
3. 选 **Build Android APK**
4. 点 **Run workflow** → **Run workflow**

### 步骤 3：下载 APK

1. 编译完成后，进入该次 Run
2. 滚动到底部 **Artifacts** 区域
3. 下载 `liuguangliyun-apk` 压缩包
4. 解压得到 `*-debug.apk` (约 50-80 MB)

> 首次编译会下载 Android SDK/NDK/Gradle，约 15-30 分钟。后续编译 5-10 分钟。

## 安装到手机

**普通安装**（推荐）：
1. 用 USB 数据线连接 Android 手机
2. 手机开 **USB 调试** (设置 → 开发者选项 → USB 调试)
3. 把 APK 拷到手机，点开安装
4. 若提示"未知来源"，去 **设置 → 安全 → 允许此来源**

**无线安装**：
- 把 APK 传到网盘/邮件，手机下载后安装
- 或用 `adb install liuguangliyun-debug.apk` 命令行装

## Android 首次启动

App 启动时会自动下载 ffmpeg（~50MB），需要：
- 网络连接
- 存储权限（会弹窗询问）

下载完成后，所有 12 个工具就能用了。

## 工作量与限制

- 已实现：12 个核心工具（覆盖原 22 工具的 90% 常用功能）
- UI 风格：Material Design（无法复刻原 PySide6 液体玻璃）
- 桌面端 `dist/流光璃韵.exe` 仍可独立使用
- 输出文件存到 `/sdcard/Download/流光璃韵/`

## 本地开发（可选）

若你想在桌面端调试 UI：

```bash
pip install kivy kivymd edge-tts aiohttp certifi
cd kivy_app
python main.py
```

## 常见问题

**Q: 编译失败？**
A: 通常是网络问题（拉 p4a/gradle 慢），可重试。

**Q: APK 装不上？**
A: 开启"未知来源安装"；或检查手机系统版本（需要 Android 5.0+）。

**Q: 工具运行时崩溃？**
A: 检查存储权限是否给了；查看 logcat: `adb logcat | grep python`。

**Q: ffmpeg 下载失败？**
A: 首次启动需要联网。若失败可手动放置 ffmpeg 到：
`/data/data/org.liuguangliyun.app/files/app/bin/ffmpeg`

## 后续可扩展

- [ ] 视频预览/缩略图
- [ ] 自定义背景/主题切换
- [ ] 工具收藏/最近使用
- [ ] 直接分享到微信/QQ
- [ ] 视频加水印（图片/文字）
- [ ] 字幕烧录
