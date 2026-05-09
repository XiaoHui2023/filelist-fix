// generate / for 内例化（仍须在 module 体内被扫到）
module torture_gen ();
  genvar gi;
  generate
    for (gi = 0; gi < 1; gi = gi + 1) begin : gloop
      torture_dep_a gi_cell ();
    end
  endgenerate
endmodule
