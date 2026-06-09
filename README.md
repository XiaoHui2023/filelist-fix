# filelist-fix

从顶层模块收集 Verilog/SystemVerilog 依赖，生成 filelist。

## 命令行参数

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| `--source` | `-s` | 多个路径 |  |  |
| `--exclude` | `-x` | 多个路径 |  | 排除 source 内的目录 |
| `--top` | `-t` | 多个模块名 |  |  |
| `--prelude` | `-p` | 多个文件路径 |  | 置于 output 前的 filelist 文件 |
| `--output` | `-o` | 文件路径 |  |  |
| `--path-style` |  | `relative` / `absolute` | `relative` | 相对路径或绝对路径 |
| `--save` |  | 文件路径 |  | 解析结果缓存 |
| `--log` | `-l` | 文件路径 |  | 运行日志 |
| `--debug-dump` |  | 目录路径 |  | 依赖分析调试输出 |

## 异常情形

### source 内找不到模块

```text
Warning: Not found module "<名>"
```

找不到模块。

也可能该模块受参数控制启用，在某些参数配置下用不到它，也不会例化它，这种情况下可以忽略警告。

### 模块名冲突

```text
Error: Duplicate definition for module "…" (use --exclude):
  …
```

同一个模块出现在多份文件里。

在 exclude 里排除多余文件，只留一个。

### 找不到 include

```text
Error: Not found include "…" in file "…"
```

需要在 prelude 中补充 `+incdir+`。

### 自动补充 incdir 时冲突

```text
Error: Ambiguous include "…" in file "…"; multiple matches (use --exclude):
  …
```

自动补充 `incdir` 时，多个目录里都有被 `include` 的文件。

需要在 prelude 中指明 `+incdir+`，或用 exclude 排除多余文件。

### prelude 路径不存在

```text
FileNotFoundError: prelude 不存在: …
```

检查 prelude 及其中 `-f`、`-v`、`-y` 引用的路径。

### include 嵌套过深

```text
RecursionError: `include` nesting too deep (possible cycle or broken tree)
```

检查 `include` 是否互相引用成环。

### 缺少 rg 或 fd

```text
FileNotFoundError: 未在 …/tools/bin 找到 rg（尝试过: …）。
```

缺少 `rg` 或 `fd` 依赖。
