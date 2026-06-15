# ====================================================
# 流光璃韵 · Android 打包配置 (buildozer.spec)
# 用法:
#   buildozer -v android debug         # 本地编译并生成 APK
#   buildozer android debug deploy      # 编译并部署到手机
#   buildozer android release           # 发布版
# ====================================================

[app]
# (str) Title of your application
title = 流光璃韵

# (str) Package name
package.name = liuguangliyun

# (str) Package domain (e.g. com.example)
package.domain = org.liuguangliyun

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,qss

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements (注入到 requirements.txt 也行, 这里更紧凑)
#  - kivy / kivymd: UI
#  - ffmpeg/edge-tts 由我们自行管理二进制
requirements = python3==3.11.6,hostpython3==3.11.6,kivy==2.3.0,kivymd==1.2.0,edge_tts==6.1.10,aiohttp==3.9.5,certifi,pyjnius,android

# (str) Presplash 颜色 (RGBA) - 朱砂 + 鎏金
# (str) Background color
# (str) Presplash filename
presplash.filename = %(source.dir)s/assets/presplash.png

# (str) Icon filename
icon.filename = %(source.dir)s/assets/icon.png

# (list) Permissions - Android 危险权限要在运行时申请
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,READ_MEDIA_IMAGES,MANAGE_EXTERNAL_STORAGE,POST_NOTIFICATIONS

# (int) Target Android API - 33+ 才能用新存储权限
android.api = 33

# (int) Minimum API
android.minapi = 21

# (str) Android NDK version
android.ndk = 25b

# (bool) Make apk debuggable (release=false)
android.debug = true

# (str) Android entry point
android.entrypoint = org.kivy.android.PythonActivity

# (str) Android additionnal libraries to use
android.add_aars =
android.add_activities = org.kivy.android.PythonActivity
android.add_jars =
android.add_res_xml = 

# (str) Java version
android.numeric_version = 1.0.0
# (str) Android application label
android.app_name = 流光璃韵
# (str) Android application package id (different from package.name)
android.private = False
# (list) Android application meta-data to set (key=value format)
android.meta_data =

# (list) Android library project directories
p4a.local_dependencies =

# (str) Packaging mode
#  - 'apk' : 普通 APK
android.build_mode = apk

# (bool) Copy app data to APK
android.copy_libs = true

# (str) 项目 ID for p4a (default: random)
p4a.bootstrap = sdl2
# (str) Bootstrap settings
p4a.bootstrap_sdl2 = --enable-framebuffer-force-hardware

# (bool) 包含额外的 ffmpeg 二进制 (从本地 assets/bin 复制)
#   我们把 ffmpeg 放进 assets/bin, 安装时复制到 /data/data/<pkg>/files/app/bin/
android.extra_assets = assets/bin/ffmpeg:bin

# (list) Patterns to exclude from source
source.exclude_patterns = build/*,.github/*,*.pyc,__pycache__/*

# (str) Supported orientations
orientation = portrait

# (bool) Show log on screen
fullscreen = 0
hide_bar = 0

# (str) 颜色
android.presplash_color = C73A3A
android.statusbar_color = 1A237E
android.background_color = F5EFE0
