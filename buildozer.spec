[app]
# 应用显示名称
title = 家庭网络控制

# 包名（必须全小写）
package.name = netblock
package.domain = org.family

# 源码目录
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas

# 应用版本
version = 1.0

# 依赖（kivy + requests 及其证书依赖）
requirements = python3,kivy,requests==2.31.0,charset-normalizer==2.1.1,certifi

# 屏幕方向
orientation = portrait
fullscreen = 0

# 安卓权限：联网
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# 最低 Android 版本（Android 7.0+）
android.minapi = 24

# 只构建 arm64 架构（近几年的手机都是），构建速度更快
# 如需兼容老手机，可改为 arm64-v8a,armeabi-v7a
android.archs = arm64-v8a

# 保留默认图标
icon.filename = 

[buildozer]
log_level = 2
warn_on_root = 1
