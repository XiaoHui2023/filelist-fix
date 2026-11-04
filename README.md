# filelist-fix

从顶层模块收集 Verilog/SystemVerilog 依赖，生成 filelist。

文档：[功能目录](docs/features.md)、[宏状态与文件顺序](docs/macro-state.md)、[定位复用与解析进度](docs/search-and-progress.md)、[显式库文件](docs/library-inputs.md)、[变更记录](CHANGELOG.md)。

## 命令行参数

| 长参数 | 短参数 | 类型 | 必填 | 默认值 | 说明 |
|--------|--------|------|:----:|--------|------|
| `--source` | `-s` | 多个路径 | ✓ |  |  |
| `--exclude` | `-x` | 多个路径 |  |  | 排除 source 内的目录 |
| `--top` | `-t` | 多个模块名 | ✓ |  |  |
| `--prelude` | `-p` | 多个文件路径 |  |  | 置于 output 前的 filelist 文件 |
| `--output` | `-o` | 文件路径 | ✓ |  |  |
| `--path-style` |  | `relative` / `absolute` |  | `relative` | 相对路径或绝对路径 |
| `--save` |  | 文件路径 |  |  | 解析结果缓存 |
| `--log` | `-l` | 文件路径 |  |  | 运行日志 |
| `--debug-dump` |  | 目录路径 |  |  | 依赖分析调试输出 |

## 使用

需要同时保留含同名 UDP/模块的库文件时，在 `-p` 指定的前导 filelist 中分别写入 `-v path`。生成清单保留全部库文件和前缀；普通源码重复定义仍报错，详见[显式库文件](docs/library-inputs.md)。

```makefile
TOOL := /path/to/tool               # 可执行文件或脚本
SOURCE += /path/to/rtl/common       # 公共 RTL 目录
SOURCE += /path/to/rtl/chip         # 子系统 RTL 目录
# EXCLUDE += /path/to/rtl/legacy    # 旧版目录，不参与收集
# EXCLUDE += /path/to/rtl/vendor    # 第三方 IP，与自研 RTL 分开
TOP += chip_top                     # 仿真顶层模块
TOP += chip_wrapper                 # 另一套顶层的模块名
# PRELUDE += /path/to/defines.f     # +define+ 与编译开关
# PRELUDE += /path/to/incdirs.f     # +incdir+ 写在 output 前的行
OUTPUT     := /path/to/out/chip.f   # 写出给仿真/综合的 filelist
# PATH_STYLE := absolute            # filelist 内写绝对路径
# SAVE       := /path/to/out/parse.db # 重复跑时复用解析结果
# LOG        := /path/to/out/run.log  # 排障日志
# DEBUG_DUMP := /path/to/out/debug    # 依赖分析中间片段

.PHONY: filelist
filelist:
	$(TOOL) -s $(SOURCE) -t $(TOP) -o $(OUTPUT)
#	-x $(EXCLUDE) -p $(PRELUDE) --path-style $(PATH_STYLE) \
#	--save $(SAVE) -l $(LOG) --debug-dump $(DEBUG_DUMP)
```

## 异常情形

### 单个源文件解析缓慢或超时

进度条在解析开始前显示当前文件，耗时较长时持续显示该文件。使用已有的 `-l run.log` 查看定位、读取、预处理、语义、实例扫描及缓存命中的耗时；嵌套阶段不能简单相加。

解析使用内置 30 秒协作预算，外部定位单次使用 120 秒截止；超时返回非零并保留已有清单。解析预算在阶段边界和扫描检查点检测，不抢占阻塞操作。只有全部依赖收集与排序成功才替换清单。原解析阈值和计时参数已移除，详见[定位与进度设计](docs/search-and-progress.md)。

### source 内找不到模块

```text
Error: Not found module "<名>"
```

当前宏配置下找不到有效的模块或 package 定义，无法生成完整 filelist。

在 source 中补充定义文件，或通过 prelude 调整条件编译宏。

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

## 发布

运行 `tools\pack.bat` 或 `./tools/pack.sh`，在 `dist/` 生成含版本与平台的可执行文件和压缩包。压缩包附带必需的依赖许可文本。
