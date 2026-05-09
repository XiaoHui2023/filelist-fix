`include "inc_chain_a.vh"

// 多层 ifdef / elsif / else / endif + 嵌套 generate-for，依赖 ni_core_leaf
module nested_pyramid ();
`ifdef WITH_DUAL
  `ifdef USE_CELLS
    `ifdef USE_CELLDEFINE
      ni_core_leaf u_ifdef_stack ();
    `else
      /* inactive: would reference ghost */
    `endif
  `else
  `endif
`elsif NEVER_FOR_THIS_TREE
  ni_core_leaf ghost_elsif ();
`else
  /* outer else 分支在本例 prelude 下不激活（WITH_DUAL 已为真）*/
`endif

  genvar gi;
  generate
    for (gi = 0; gi < 1; gi = gi + 1) begin : outer_g
      genvar gj;
      generate
        for (gj = 0; gj < 1; gj = gj + 1) begin : inner_g
          ni_core_leaf u_gen_nested ();
        end
      endgenerate
    end
  endgenerate
endmodule
