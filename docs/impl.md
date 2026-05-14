# IMPL

## sink.progress_sink

让使用者在一次运行中持续看到所处阶段与解析相关进展，而不必仅靠事后日志推断进度。

**对应 API**

- `OnProgressAPI`
- `OnSourceParsedAPI`

## sink.warnings_sink

将模块未找到、内部索引不一致等情况转为面向人的告警或说明，避免无声跳过。模块定义未命中时写 **WARNING**（`Not found module "…"`）到上下文 logger（与 **`-l`** 文件日志一致）。

**对应 API**

- `OnModuleResolveMissAPI`
- `OnModuleIndexInconsistentAPI`

## sink.filelist_write_sink

将已确定的完整 filelist 按用户指定的输出路径写出为最终文件。

**对应 API**

- `OnFilelistWriteAPI`

## sink.save_lifecycle_sink

在用户启用解析结果复用时，于一次构建结束时结束与该选项相关的会话期占用，避免资源悬挂。

**对应 API**

- `OnSessionEndAPI`

## resolve.verilog_text_resolve

为依赖扫描准备单层源码的可读形态：在 **squeeze** 中依次弱化注释与过程块、assign/wire/parameter 等声明行、各 module 体内的端口头，再交给扫描；本节不写具体实现步骤。

**对应 API**

- `JoinContinuedLinesAPI`
- `StripVerilogCommentsAPI`
- `DropAlwaysishBlocksAPI`
- `SqueezeForDependencyScanAPI`
- `ScanVerilogForDependenciesAPI`
