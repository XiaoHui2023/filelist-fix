# filelist-fix

从顶层模块收集 Verilog/SystemVerilog 依赖并生成 filelist。

## 命令行参数

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| `--source` | `-S` | 路径（可多次指定） | 必填 | 检索根目录或文件；每出现一次增加一项 |
| `--top` | `-t` | 文本（可多次指定） | 必填 | 顶层模块名；每出现一次增加一项 |
| `--prelude` | `-p` | 文件路径（可多次指定） |  | prelude：`+define+` / `+incdir+` 或普通行，顺序保留；可省略 |
| `--output` | `-o` | 文件路径 | 必填 | 写出最终 filelist（先 prelude 行，再排序后的路径） |
| `--path-style` |  | `relative` / `absolute` | `relative` | filelist 正文中的源路径：相对 **输出文件所在目录**，或绝对路径；`+define+` / `+incdir+` 等仍只参与解析、不写入正文 |
| `--save` | `-s` | 文件路径 |  | SQLite 解析缓存（扩展名常用 **`.db`**）；源未变（mtime/size）时可复用；省略则不启用 |
| `--log` | `-l` | 文件路径 |  | 日志；省略时不写文件 |

## API

契约与类型说明见 [`docs/api.md`](docs/api.md)。

## IMPL

模块与订阅 API 说明见 [`docs/impl.md`](docs/impl.md)。
