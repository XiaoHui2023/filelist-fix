# filelist-fix

从顶层模块收集 Verilog/SystemVerilog 依赖，生成 filelist。

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
| `--parse-timings` |  | JSON 路径 |  |  | 每个源文件的各阶段耗时、缓存命中与失败详情 |
| `--parse-timeout` |  | 秒数 |  | `30` | 单个源文件及其 include 的解析预算；`0` 关闭 |
| `--slow-file-seconds` |  | 秒数 |  | `5` | 尚未解析完时提示当前文件、阶段和已用时间；`0` 关闭 |

## 使用

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

使用 `-l run.log --parse-timings timing.json` 查看读取、预处理、语义、压缩子阶段、实例扫描和诊断耗时。计时文件须使用 `.json` 后缀，并与清单、缓存、日志和显式输入使用不同路径。缓存命中单独记录为 `cache`；include 阶段标注实际文件路径。嵌套阶段包含其子阶段耗时，不能简单相加。

默认在 5 秒时提示仍在解析的文件和阶段；超过 30 秒预算返回非零，保留已有清单。预算在阶段边界和扫描检查点检测，不抢占阻塞中的系统调用或 Python 正则引擎。较慢存储或超大工程可以调整 `--parse-timeout`。清单全部解析、依赖闭包和排序成功后才通过同目录临时文件替换；失败清理临时文件。

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
