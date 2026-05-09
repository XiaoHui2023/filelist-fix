# ripgrep（rg）与 fd 本地二进制

本目录脚本用于把 **静态/独立** 的 `rg` 与 `fd` 下载到仓库下的 `tools/bin/`，供本项目的文件搜索使用（不污染系统路径）。

## 目录约定

执行完成后应存在：

- `tools/bin/rg`（Linux/macOS）或 `tools/bin/rg.exe`（Windows）
- `tools/bin/fd`（Linux/macOS）或 `tools/bin/fd.exe`（Windows）

程序会优先使用 `tools/bin` 下的可执行文件；若无则回退到 `PATH`。

## 官方发布页（自行核对最新版本与校验和）

- ripgrep: https://github.com/BurntSushi/ripgrep/releases
- fd: https://github.com/sharkdp/fd/releases

各资产命名随平台与架构变化；脚本内列出了当前维护者常用的命名模式，若 404 请到上述发布页替换为当前版本号与文件名。

## Linux / macOS

```bash
chmod +x tools/download_rg_fd.sh
./tools/download_rg_fd.sh
```

## Windows

在「开发者命令提示符」或 PowerShell 中：

```bat
tools\download_rg_fd.bat
```

需要已安装 PowerShell 5+（系统自带）。脚本使用 `Invoke-WebRequest` 下载。
