[app]
title = Yandex Music Downloader
package.name = ymd
package.domain = com.finexstudio

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = screenshots,.git,.github,__pycache__,bin,.buildozer

p4a.branch = develop

version = 1.2.1

requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.2.1,yandex-music,requests,urllib3,certifi,chardet,idna,android,pillow

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
