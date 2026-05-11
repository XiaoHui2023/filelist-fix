# ripgrep（rg）与 fd 本地二进制

本目录脚本用于把 **静态/独立** 的 `rg` 与 `fd` 下载到仓库下的 `tools/bin/`，供本项目的文件搜索使用（不污染系统路径）。

## 目录约定

执行完成后应存在（**运行本工具前须已就位**，程序只从此目录加载，**不回退 PATH**）：

- `tools/bin/rg`（Linux/macOS）或 `tools/bin/rg.exe`（Windows）
- `tools/bin/fd`（Linux/macOS）或 `tools/bin/fd.exe`（Windows）

缺失时程序启动即抛出 **`FileNotFoundError`**，请先运行下文下载脚本。

## 官方发布页（自行核对最新版本与校验和）

- ripgrep: https://github.com/BurntSushi/ripgrep/releases
- fd: https://github.com/sharkdp/fd/releases

各资产命名随平台与架构变化；脚本内列出了当前维护者常用的命名模式，若 404 请到上述发布页替换为当前版本号与文件名。

## Linux / macOS

```bash
chmod +x tools/download_rg_fd.sh
./tools/download_rg_fd.sh
```

## 一键打包（PyInstaller；Linux 再 staticx）

在仓库根执行（会先确保 `tools/bin` 的 rg、fd，再使用根目录 `.venv`，无则创建）：

```bash
chmod +x tools/pack.sh
./tools/pack.sh
```

Linux 另需系统安装 **`patchelf`**（如 `sudo apt install patchelf`）。产物：**`dist/filelist-fix`**（Linux 为 staticx 处理后的单文件）或 **`dist/filelist-fix.exe`**（Windows）。**macOS** 当前脚本跳过 staticx，仅 PyInstaller 产物。

## Windows

在「开发者命令提示符」或 PowerShell 中：

```bat
tools\download_rg_fd.bat
```

需要已安装 PowerShell 5+（系统自带）。脚本使用 `Invoke-WebRequest` 下载。
