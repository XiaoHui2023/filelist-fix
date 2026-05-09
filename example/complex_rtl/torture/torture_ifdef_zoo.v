// Preprocessor zoo: ifndef / ifdef / elsif / else combinations (active paths use prelude macros only).
module torture_ifdef_zoo ();

  // ifndef: branch active when macro is absent (none of these are in prelude).
`ifndef TORTURE_ZOO_UNDEF_A
  torture_dep_a u_ifndef_plain ();
`endif

  // Nested ifndef under ifdef WITH_DUAL (prelude): inner DISABLE_TORTURE_ZOO_AUX is absent -> include dep_b.
`ifdef WITH_DUAL
  `ifndef DISABLE_TORTURE_ZOO_AUX
    torture_dep_b u_ifndef_nested ();
  `else
    ni_core_leaf u_should_skip_when_aux_disabled ();
  `endif
`endif

  // ifdef chain where first/elsif macros are absent -> else branch pulls ni_core_leaf.
`ifdef TORTURE_ZOO_NEVER_DEFINED_X
  torture_dep_a u_bad_x ();
`elsif TORTURE_ZOO_NEVER_DEFINED_Y
  torture_dep_b u_bad_y ();
`else
  ni_core_leaf u_from_final_else ();
`endif

  // ifndef / elsif / else: only first guard is true when A,B absent.
`ifndef TORTURE_ZOO_GUARD_A
  torture_dep_a u_ifndef_elsif_first ();
`elsif TORTURE_ZOO_GUARD_B
  torture_dep_b u_ifndef_elsif_second ();
`else
  ni_core_leaf u_ifndef_elsif_else ();
`endif

endmodule
