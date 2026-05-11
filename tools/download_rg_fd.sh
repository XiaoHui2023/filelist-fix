#!/usr/bin/env bash
# 下载 ripgrep 与 fd 到 tools/bin（按架构选发布包；Linux x86_64/aarch64 的 fd 使用 musl 包以降低对 glibc 版本的要求）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/tools/bin"
mkdir -p "$BIN"

# 版本可按需上调；若 404 请到 GitHub Releases 更新。
RG_VER="14.1.1"
FD_VER="10.2.0"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

rg_asset=""
fd_asset=""
rg_exe="rg"
fd_exe="fd"

case "$OS" in
  linux)
    case "$ARCH" in
      x86_64|amd64)
        rg_asset="ripgrep-${RG_VER}-x86_64-unknown-linux-musl.tar.gz"
        fd_asset="fd-v${FD_VER}-x86_64-unknown-linux-musl.tar.gz"
        ;;
      aarch64|arm64)
        rg_asset="ripgrep-${RG_VER}-aarch64-unknown-linux-gnu.tar.gz"
        fd_asset="fd-v${FD_VER}-aarch64-unknown-linux-musl.tar.gz"
        ;;
      *)
        echo "不支持的架构: $ARCH"; exit 1 ;;
    esac
    ;;
  darwin)
    case "$ARCH" in
      x86_64|amd64)
        rg_asset="ripgrep-${RG_VER}-x86_64-apple-darwin.tar.gz"
        fd_asset="fd-v${FD_VER}-x86_64-apple-darwin.tar.gz"
        ;;
      arm64|aarch64)
        rg_asset="ripgrep-${RG_VER}-aarch64-apple-darwin.tar.gz"
        fd_asset="fd-v${FD_VER}-aarch64-apple-darwin.tar.gz"
        ;;
      *)
        echo "不支持的架构: $ARCH"; exit 1 ;;
    esac
    ;;
  *)
    echo "不支持的操作系统: $OS"; exit 1 ;;
esac

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "==> ripgrep $RG_VER ($rg_asset)"
curl -fsSL -o "$tmp/rg.tgz" "https://github.com/BurntSushi/ripgrep/releases/download/${RG_VER}/${rg_asset}"
tar -xzf "$tmp/rg.tgz" -C "$tmp"
rg_path="$(find "$tmp" -type f -name rg | head -n 1)"
if [[ -z "$rg_path" ]]; then echo "解压后未找到 rg"; exit 1; fi
install -m0755 "$rg_path" "$BIN/$rg_exe"

echo "==> fd $FD_VER ($fd_asset)"
curl -fsSL -o "$tmp/fd.tgz" "https://github.com/sharkdp/fd/releases/download/v${FD_VER}/${fd_asset}"
tar -xzf "$tmp/fd.tgz" -C "$tmp"
fd_path="$(find "$tmp" -type f -name fd | head -n 1)"
if [[ -z "$fd_path" ]]; then echo "解压后未找到 fd"; exit 1; fi
install -m0755 "$fd_path" "$BIN/$fd_exe"

echo "完成: $BIN/$rg_exe 与 $BIN/$fd_exe"
