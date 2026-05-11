# filelist-fix

从顶层模块收集 Verilog/SystemVerilog 依赖并生成 filelist。

## 命令行参数

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| `--source` | `-s` | 路径（可多次指定） | 必填 | 检索根目录或文件；同一 `-s` 后可跟多个路径（`-s a b`），也可多次写 `-s`（`-s a -s b`） |
| `--exclude` | `-x` | 路径（可多次指定） |  | 在 `--source` 范围内排除该文件或整段目录树；路径须存在；同上支持 `-x a b` 与多次 `-x` |
| `--top` | `-t` | 文本（可多次指定） | 必填 | 顶层模块名；同上支持 `-t m1 m2` 与多次 `-t` |
| `--prelude` | `-p` | 文件路径（可多次指定） |  | prelude：`+define+` / `+incdir+` 或普通行，顺序保留；可省略；同上支持 `-p a b` 与多次 `-p` |
| `--output` | `-o` | 文件路径 | 必填 | 写出最终 filelist（先 prelude 行，再排序后的路径） |
| `--path-style` |  | `relative` / `absolute` | `relative` | filelist 正文中的源路径：相对 **输出文件所在目录**，或绝对路径；`+define+` / `+incdir+` 等仍只参与解析、不写入正文 |
| `--save` |  | 文件路径 |  | SQLite 解析缓存（扩展名常用 **`.db`**）；源未变（mtime/size）时可复用；省略则不启用 |
| `--log` | `-l` | 文件路径 |  | 写入 **DEBUG** 级别日志（检索模块、命中路径、解析到的定义/引用、入队模块等）；省略时不写文件 |

未在检索根下找到定义文件的引用模块，运行结束会在 **stderr** 逐行输出一行说明；其中 **`Warning`** 字样为黄色（24 位色）。指定 **`-l` / `--log`** 时，同一批未命中模块还会以 **WARNING** 级别写入日志文件。

## API

API 类型与说明见 [`docs/api.md`](docs/api.md)。

## IMPL

模块与订阅 API 说明见 [`docs/impl.md`](docs/impl.md)。
