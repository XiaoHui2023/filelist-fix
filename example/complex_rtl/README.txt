complex_rtl — 刻意复杂化的 Verilog/SystemVerilog 黄金样例
============================================================

目录结构（简要）：

  top_chip.v          顶层：串联多枚 `include，模块体由若干 .vh 拼接
  common/             嵌套 include、全局宏、带参 `define 试验
  pieces/             端口/连线 generate、celldefine 片段、多级 include 链 (chain_d→e→f)
  hier/               叶子与中层、generate-for、单文件双 module (dual_mods.sv)

用途：
- 示范「多文件通过 `include` 拼成逻辑整文件」；
- 覆盖 `ifdef/elsif/define/undef、celldefine、generate、层次实例化、单文件多 module（fd/rg 分工）`；
- 作为 example 脚本与手工调试解析器的共同输入。

运行：
  在仓库根执行 example.bat（或 python example/demo.py），会在 example/generated/ 写入
  run_prelude.f（运行时 +incdir+）与 demo_filelist.f；generated/ 已加入 .gitignore。
