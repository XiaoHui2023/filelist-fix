`include "common/build_flags.vh"
`include "common/global_macros.vh"
`include "common/param_macro.vh"
`include "common/outer_include.vh"
`include "pieces/chain_d.vh"

module top_chip (
`include "pieces/ports_inner.vh"
);

`include "pieces/wires_top.vh"

  mid_math i_math ();
  mid_memctl i_mem ();

`ifdef WITH_DUAL
  mod_b i_dual ();
`endif

`include "pieces/gen_mesh.vh"
`include "pieces/cellish_frag.vh"
`include "hier/wrapper_tail.vh"

endmodule
