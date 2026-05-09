module mid_math ();
  parameter integer N = 3;
  genvar i;
  generate
    for (i = 0; i < N; i = i + 1) begin : g_alu_row
      leaf_alu u_alu ();
    end
  endgenerate
endmodule
