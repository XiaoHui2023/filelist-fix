`ifdef WITH_DUAL
`define DUAL_OK 1
`elsif FORCE_SINGLE
`define DUAL_OK 0
`else
`define DUAL_OK 1
`endif

`undef UNUSED_MACRO_TOKEN
