// 时序/过程噪声：不应被误识别为模块例化
module torture_timing ();
  reg clk, rst_n;
  wire a, b;

  initial #0.1 rst_n = 0;
  initial #10 clk = 0;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
    end else begin
    end
  end

  always_ff @(posedge clk) begin
    #1;
  end

  always_comb begin
    a = b;
  end

  assign a = (posedge clk);
endmodule
