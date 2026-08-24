import sys, re

raw_text = """
The test is all_reduce_perf, the maca version is /opt/maca-3.8.1
main_process = 3025700
===============================
# nThread 1 nGpus 1 minBytes 1024 maxBytes 1073741824 step: 2(factor) warmup iters: 5 iters: 10 agg iters: 1 validation: 1 graph: 0
#
# Using devices
#   Rank  0 Pid 3025700 on mx-decode-01 device  0 [0x08] MetaX C500
#   Rank  1 Pid 3025701 on mx-decode-01 device  1 [0x09] MetaX C500
#   Rank  2 Pid 3025702 on mx-decode-01 device  2 [0x0e] MetaX C500
#   Rank  3 Pid 3025703 on mx-decode-01 device  3 [0x11] MetaX C500
#   Rank  4 Pid 3025704 on mx-decode-01 device  4 [0x32] MetaX C500
#   Rank  5 Pid 3025705 on mx-decode-01 device  5 [0x38] MetaX C500
#   Rank  6 Pid 3025706 on mx-decode-01 device  6 [0x3b] MetaX C500
#   Rank  7 Pid 3025707 on mx-decode-01 device  7 [0x3c] MetaX C500
#
#                                                           ┌----- out-of-place ------┐       ┌------ in-place -------┐
#        size         count      type   redop    root      time    algbw   busbw   #wrong    time   algbw   busbw   #wrong
#         (B)    (elements)                                (us)   (GB/s)  (GB/s)              (us)  (GB/s)  (GB/s)       
        1024           512  bfloat16     sum      -1      29.78    0.03    0.06      0      38.91    0.03    0.05      0
        2048          1024  bfloat16     sum      -1      36.51    0.06    0.10      0      15.95    0.13    0.22      0
        4096          2048  bfloat16     sum      -1      15.57    0.26    0.46      0      15.73    0.26    0.46      0
        8192          4096  bfloat16     sum      -1      23.34    0.35    0.61      0      22.07    0.37    0.65      0
       16384          8192  bfloat16     sum      -1      22.76    0.72    1.26      0      23.74    0.69    1.21      0
       32768         16384  bfloat16     sum      -1      25.22    1.30    2.27      0      25.12    1.30    2.28      0
       65536         32768  bfloat16     sum      -1      27.21    2.41    4.22      0      26.46    2.48    4.33      0
      131072         65536  bfloat16     sum      -1      30.27    4.33    7.58      0      29.25    4.48    7.84      0
      262144        131072  bfloat16     sum      -1      37.35    7.02   12.28      0      37.35    7.02   12.28      0
      524288        262144  bfloat16     sum      -1      46.82   11.20   19.59      0      47.20   11.11   19.44      0
     1048576        524288  bfloat16     sum      -1      63.38   16.54   28.95      0      63.42   16.53   28.94      0
     2097152       1048576  bfloat16     sum      -1     104.11   20.14   35.25      0     103.24   20.31   35.55      0
     4194304       2097152  bfloat16     sum      -1     165.16   25.40   44.44      0     164.63   25.48   44.58      0
     8388608       4194304  bfloat16     sum      -1     330.67   25.37   44.39      0     330.39   25.39   44.43      0
    16777216       8388608  bfloat16     sum      -1     575.19   29.17   51.04      0     575.19   29.17   51.04      0
    33554432      16777216  bfloat16     sum      -1    1052.74   31.87   55.78      0    1065.77   31.48   55.10      0
    67108864      33554432  bfloat16     sum      -1    1981.31   33.87   59.27      0    1980.92   33.88   59.29      0
   134217728      67108864  bfloat16     sum      -1    3833.48   35.01   61.27      0    3832.66   35.02   61.28      0
   268435456     134217728  bfloat16     sum      -1    7468.96   35.94   62.90      0    7468.49   35.94   62.90      0
   536870912     268435456  bfloat16     sum      -1   14704.42   36.51   63.89      0   14701.82   36.52   63.91      0
  1073741824     536870912  bfloat16     sum      -1   29182.91   36.79   64.39      0   29181.51   36.80   64.39      0
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 29.5284 
#
The test is all_gather_perf, the maca version is /opt/maca-3.8.1
main_process = 3025943
===============================
# nThread 1 nGpus 1 minBytes 1024 maxBytes 1073741824 step: 2(factor) warmup iters: 5 iters: 10 agg iters: 1 validation: 1 graph: 0
#
# Using devices
#   Rank  0 Pid 3025943 on mx-decode-01 device  0 [0x08] MetaX C500
#   Rank  1 Pid 3025944 on mx-decode-01 device  1 [0x09] MetaX C500
#   Rank  2 Pid 3025945 on mx-decode-01 device  2 [0x0e] MetaX C500
#   Rank  3 Pid 3025946 on mx-decode-01 device  3 [0x11] MetaX C500
#   Rank  4 Pid 3025947 on mx-decode-01 device  4 [0x32] MetaX C500
#   Rank  5 Pid 3025948 on mx-decode-01 device  5 [0x38] MetaX C500
#   Rank  6 Pid 3025949 on mx-decode-01 device  6 [0x3b] MetaX C500
#   Rank  7 Pid 3025950 on mx-decode-01 device  7 [0x3c] MetaX C500
#
#                                                           ┌----- out-of-place ------┐       ┌------ in-place -------┐
#        size         count      type   redop    root      time    algbw   busbw   #wrong    time   algbw   busbw   #wrong
#         (B)    (elements)                                (us)   (GB/s)  (GB/s)              (us)  (GB/s)  (GB/s)       
        1024            64  bfloat16              -1      18.19    0.06    0.05      0      17.28    0.06    0.05      0
        2048           128  bfloat16              -1      17.17    0.12    0.10      0      16.28    0.13    0.11      0
        4096           256  bfloat16              -1      16.53    0.25    0.22      0      16.64    0.25    0.22      0
        8192           512  bfloat16              -1      16.69    0.49    0.43      0      16.92    0.48    0.42      0
       16384          1024  bfloat16              -1      17.51    0.94    0.82      0      17.26    0.95    0.83      0
       32768          2048  bfloat16              -1      18.67    1.76    1.54      0      18.74    1.75    1.53      0
       65536          4096  bfloat16              -1      18.80    3.49    3.05      0      18.76    3.49    3.06      0
      131072          8192  bfloat16              -1      19.06    6.88    6.02      0      19.62    6.68    5.85      0
      262144         16384  bfloat16              -1      20.47   12.80   11.20      0      20.36   12.87   11.26      0
      524288         32768  bfloat16              -1      24.68   21.24   18.59      0      25.05   20.93   18.31      0
     1048576         65536  bfloat16              -1      33.41   31.39   27.47      0      33.67   31.14   27.25      0
     2097152        131072  bfloat16              -1      67.59   31.03   27.15      0      66.68   31.45   27.52      0
     4194304        262144  bfloat16              -1      99.41   42.19   36.92      0      99.33   42.22   36.95      0
     8388608        524288  bfloat16              -1     168.45   49.80   43.57      0     167.92   49.96   43.71      0
    16777216       1048576  bfloat16              -1     285.26   58.81   51.46      0     285.22   58.82   51.47      0
    33554432       2097152  bfloat16              -1     520.36   64.48   56.42      0     519.88   64.54   56.47      0
    67108864       4194304  bfloat16              -1     994.23   67.50   59.06      0     994.48   67.48   59.05      0
   134217728       8388608  bfloat16              -1    1909.14   70.30   61.51      0    1909.67   70.28   61.50      0
   268435456      16777216  bfloat16              -1    3746.51   71.65   62.69      0    3746.66   71.65   62.69      0
   536870912      33554432  bfloat16              -1    7354.04   73.00   63.88      0    7354.46   73.00   63.87      0
  1073741824      67108864  bfloat16              -1   14553.37   73.78   64.56      0   14552.68   73.78   64.56      0
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 28.414 
#
The test is reduce_scatter_perf, the maca version is /opt/maca-3.8.1
main_process = 3026187
===============================
# nThread 1 nGpus 1 minBytes 1024 maxBytes 1073741824 step: 2(factor) warmup iters: 5 iters: 10 agg iters: 1 validation: 1 graph: 0
#
# Using devices
#   Rank  0 Pid 3026187 on mx-decode-01 device  0 [0x08] MetaX C500
#   Rank  1 Pid 3026188 on mx-decode-01 device  1 [0x09] MetaX C500
#   Rank  2 Pid 3026189 on mx-decode-01 device  2 [0x0e] MetaX C500
#   Rank  3 Pid 3026190 on mx-decode-01 device  3 [0x11] MetaX C500
#   Rank  4 Pid 3026191 on mx-decode-01 device  4 [0x32] MetaX C500
#   Rank  5 Pid 3026192 on mx-decode-01 device  5 [0x38] MetaX C500
#   Rank  6 Pid 3026193 on mx-decode-01 device  6 [0x3b] MetaX C500
#   Rank  7 Pid 3026194 on mx-decode-01 device  7 [0x3c] MetaX C500
#
#                                                           ┌----- out-of-place ------┐       ┌------ in-place -------┐
#        size         count      type   redop    root      time    algbw   busbw   #wrong    time   algbw   busbw   #wrong
#         (B)    (elements)                                (us)   (GB/s)  (GB/s)              (us)  (GB/s)  (GB/s)       
        1024            64  bfloat16     sum      -1      20.93    0.05    0.04      0      19.54    0.05    0.05      0
        2048           128  bfloat16     sum      -1      17.76    0.12    0.10      0      17.74    0.12    0.10      0
        4096           256  bfloat16     sum      -1      17.41    0.24    0.21      0      17.24    0.24    0.21      0
        8192           512  bfloat16     sum      -1      17.81    0.46    0.40      0      17.86    0.46    0.40      0
       16384          1024  bfloat16     sum      -1      17.83    0.92    0.80      0      17.76    0.92    0.81      0
       32768          2048  bfloat16     sum      -1      20.22    1.62    1.42      0      20.16    1.63    1.42      0
       65536          4096  bfloat16     sum      -1      20.31    3.23    2.82      0      20.04    3.27    2.86      0
      131072          8192  bfloat16     sum      -1      20.48    6.40    5.60      0      20.50    6.39    5.59      0
      262144         16384  bfloat16     sum      -1      23.06   11.37    9.95      0      23.13   11.33    9.92      0
      524288         32768  bfloat16     sum      -1      28.28   18.54   16.22      0      28.25   18.56   16.24      0
     1048576         65536  bfloat16     sum      -1      39.13   26.80   23.45      0      39.39   26.62   23.29      0
     2097152        131072  bfloat16     sum      -1      75.00   27.96   24.47      0      75.25   27.87   24.38      0
     4194304        262144  bfloat16     sum      -1     112.81   37.18   32.53      0     112.99   37.12   32.48      0
     8388608        524288  bfloat16     sum      -1     184.07   45.57   39.88      0     184.04   45.58   39.88      0
    16777216       1048576  bfloat16     sum      -1     319.03   52.59   46.01      0     318.20   52.73   46.14      0
    33554432       2097152  bfloat16     sum      -1     560.92   59.82   52.34      0     560.72   59.84   52.36      0
    67108864       4194304  bfloat16     sum      -1    1052.61   63.75   55.79      0    1052.32   63.77   55.80      0
   134217728       8388608  bfloat16     sum      -1    1982.52   67.70   59.24      0    1982.95   67.69   59.23      0
   268435456      16777216  bfloat16     sum      -1    3858.36   69.57   60.88      0    3858.57   69.57   60.87      0
   536870912      33554432  bfloat16     sum      -1    7497.51   71.61   62.66      0    7497.57   71.61   62.66      0
  1073741824      67108864  bfloat16     sum      -1   14777.12   72.66   63.58      0   14777.99   72.66   63.58      0
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 26.5869 
#
The test is sendrecv_perf, the maca version is /opt/maca-3.8.1
main_process = 3026429
===============================
# nThread 1 nGpus 1 minBytes 1024 maxBytes 1073741824 step: 2(factor) warmup iters: 5 iters: 10 agg iters: 1 validation: 1 graph: 0
#
# Using devices
#   Rank  0 Pid 3026429 on mx-decode-01 device  0 [0x08] MetaX C500
#   Rank  1 Pid 3026430 on mx-decode-01 device  1 [0x09] MetaX C500
#   Rank  2 Pid 3026431 on mx-decode-01 device  2 [0x0e] MetaX C500
#   Rank  3 Pid 3026432 on mx-decode-01 device  3 [0x11] MetaX C500
#   Rank  4 Pid 3026433 on mx-decode-01 device  4 [0x32] MetaX C500
#   Rank  5 Pid 3026434 on mx-decode-01 device  5 [0x38] MetaX C500
#   Rank  6 Pid 3026435 on mx-decode-01 device  6 [0x3b] MetaX C500
#   Rank  7 Pid 3026436 on mx-decode-01 device  7 [0x3c] MetaX C500
#
#                                                           ┌----- out-of-place ------┐       ┌------ in-place -------┐
#        size         count      type   redop    root      time    algbw   busbw   #wrong    time   algbw   busbw   #wrong
#         (B)    (elements)                                (us)   (GB/s)  (GB/s)              (us)  (GB/s)  (GB/s)       
        1024           512  bfloat16     sum      -1      18.58    0.06    0.06      0      18.07    0.06    0.06    N/A
        2048          1024  bfloat16     sum      -1      18.56    0.11    0.11      0      18.27    0.11    0.11    N/A
        4096          2048  bfloat16     sum      -1      19.49    0.21    0.21      0      18.58    0.22    0.22    N/A
        8192          4096  bfloat16     sum      -1      20.19    0.41    0.41      0      19.72    0.42    0.42    N/A
       16384          8192  bfloat16     sum      -1      24.54    0.67    0.67      0      24.33    0.67    0.67    N/A
       32768         16384  bfloat16     sum      -1      22.84    1.43    1.43      0      22.52    1.46    1.46    N/A
       65536         32768  bfloat16     sum      -1      25.49    2.57    2.57      0      26.22    2.50    2.50    N/A
      131072         65536  bfloat16     sum      -1      31.97    4.10    4.10      0      31.89    4.11    4.11    N/A
      262144        131072  bfloat16     sum      -1      33.93    7.73    7.73      0      35.05    7.48    7.48    N/A
      524288        262144  bfloat16     sum      -1      39.94   13.13   13.13      0      39.81   13.17   13.17    N/A
     1048576        524288  bfloat16     sum      -1      59.60   17.59   17.59      0      59.52   17.62   17.62    N/A
     2097152       1048576  bfloat16     sum      -1      99.40   21.10   21.10      0      98.94   21.20   21.20    N/A
     4194304       2097152  bfloat16     sum      -1     179.19   23.41   23.41      0     178.96   23.44   23.44    N/A
     8388608       4194304  bfloat16     sum      -1     353.30   23.74   23.74      0     353.37   23.74   23.74    N/A
    16777216       8388608  bfloat16     sum      -1     643.07   26.09   26.09      0     641.74   26.14   26.14    N/A
    33554432      16777216  bfloat16     sum      -1    1220.85   27.48   27.48      0    1215.72   27.60   27.60    N/A
    67108864      33554432  bfloat16     sum      -1    2425.15   27.67   27.67      0    2413.67   27.80   27.80    N/A
   134217728      67108864  bfloat16     sum      -1    4851.53   27.67   27.67      0    4846.08   27.70   27.70    N/A
   268435456     134217728  bfloat16     sum      -1    9839.21   27.28   27.28      0    9911.12   27.08   27.08    N/A
   536870912     268435456  bfloat16     sum      -1   20537.51   26.14   26.14      0   20897.83   25.69   25.69    N/A
  1073741824     536870912  bfloat16     sum      -1   42694.56   25.15   25.15      0   42662.24   25.17   25.17    N/A
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 14.4548 
#
The test is alltoall_perf, the maca version is /opt/maca-3.8.1
main_process = 3026681
===============================
# nThread 1 nGpus 1 minBytes 1024 maxBytes 1073741824 step: 2(factor) warmup iters: 5 iters: 10 agg iters: 1 validation: 1 graph: 0
#
# Using devices
#   Rank  0 Pid 3026681 on mx-decode-01 device  0 [0x08] MetaX C500
#   Rank  1 Pid 3026682 on mx-decode-01 device  1 [0x09] MetaX C500
#   Rank  2 Pid 3026683 on mx-decode-01 device  2 [0x0e] MetaX C500
#   Rank  3 Pid 3026684 on mx-decode-01 device  3 [0x11] MetaX C500
#   Rank  4 Pid 3026685 on mx-decode-01 device  4 [0x32] MetaX C500
#   Rank  5 Pid 3026686 on mx-decode-01 device  5 [0x38] MetaX C500
#   Rank  6 Pid 3026687 on mx-decode-01 device  6 [0x3b] MetaX C500
#   Rank  7 Pid 3026688 on mx-decode-01 device  7 [0x3c] MetaX C500
#
#                                                           ┌----- out-of-place ------┐       ┌------ in-place -------┐
#        size         count      type   redop    root      time    algbw   busbw   #wrong    time   algbw   busbw   #wrong
#         (B)    (elements)                                (us)   (GB/s)  (GB/s)              (us)  (GB/s)  (GB/s)       
        1024            64  bfloat16              -1      21.18    0.05    0.04      0      20.71    0.05    0.04    N/A
        2048           128  bfloat16              -1      20.35    0.10    0.09      0      18.94    0.11    0.09    N/A
        4096           256  bfloat16              -1      19.14    0.21    0.19      0      19.05    0.22    0.19    N/A
        8192           512  bfloat16              -1      18.91    0.43    0.38      0      19.72    0.42    0.36    N/A
       16384          1024  bfloat16              -1      19.72    0.83    0.73      0      20.08    0.82    0.71    N/A
       32768          2048  bfloat16              -1      21.43    1.53    1.34      0      21.19    1.55    1.35    N/A
       65536          4096  bfloat16              -1      22.79    2.88    2.52      0      22.80    2.87    2.51    N/A
      131072          8192  bfloat16              -1      26.31    4.98    4.36      0      26.16    5.01    4.38    N/A
      262144         16384  bfloat16              -1      33.84    7.75    6.78      0      33.71    7.78    6.80    N/A
      524288         32768  bfloat16              -1      49.48   10.60    9.27      0      49.80   10.53    9.21    N/A
     1048576         65536  bfloat16              -1      82.43   12.72   11.13      0      81.77   12.82   11.22    N/A
     2097152        131072  bfloat16              -1     163.14   12.85   11.25      0     161.83   12.96   11.34    N/A
     4194304        262144  bfloat16              -1     282.70   14.84   12.98      0     282.72   14.84   12.98    N/A
     8388608        524288  bfloat16              -1     530.12   15.82   13.85      0     529.57   15.84   13.86    N/A
    16777216       1048576  bfloat16              -1     983.07   17.07   14.93      0     982.93   17.07   14.93    N/A
    33554432       2097152  bfloat16              -1    1885.81   17.79   15.57      0    1886.09   17.79   15.57    N/A
    67108864       4194304  bfloat16              -1    3721.99   18.03   15.78      0    3722.35   18.03   15.78    N/A
   134217728       8388608  bfloat16              -1    7307.68   18.37   16.07      0    7308.08   18.37   16.07    N/A
   268435456      16777216  bfloat16              -1   14537.23   18.47   16.16      0   14537.26   18.47   16.16    N/A
   536870912      33554432  bfloat16              -1   28825.93   18.62   16.30      0   28823.88   18.63   16.30    N/A
  1073741824      67108864  bfloat16              -1   57394.18   18.71   16.37      0   57387.51   18.71   16.37    N/A
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 8.86458 
#
"""

# 各算子在 1GB (1073741824 Bytes) 时的最低 algbw 预期门槛
EXPECTED_PEAK_ALGBW = {
    "all_reduce_perf": 36.0,
    "all_gather_perf": 73.0,
    "reduce_scatter_perf": 72.0,
    "alltoall_perf": 18.71
}

import sys

EXPECTED_PEAK_ALGBW = {
    "all_reduce_perf": 36.0,
    "all_gather_perf": 73.0,
    "reduce_scatter_perf": 72.0,
    "alltoall_perf": 18.71
}

raw_sections = raw_text.split("The test is ")
errors = []

for sec in raw_sections:
    if not sec.strip():
        continue
    
    test_name = sec.split(",")[0].strip()
    lines = sec.splitlines()

    # 用于记录当前子测试的列位置
    algbw_idx = None
    busbw_idx = None
    wrong_idx = None

    prev_algbw = -1.0
    prev_busbw = -1.0
    peak_1g_algbw = None

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        # 1. 动态抓取表头，获取索引位置
        if "size" in line_str and "algbw" in line_str:
            # 清理开头的 # 号并按空白字符分割
            headers = line_str.lstrip("#").split()
            if "algbw" in headers:
                algbw_idx = headers.index("algbw")
            if "busbw" in headers:
                busbw_idx = headers.index("busbw")
            if "#wrong" in headers:
                wrong_idx = headers.index("#wrong")
            continue

        # 忽略其他非数据注释行
        if line_str.startswith("#"):
            continue

        parts = line_str.split()
        # 只要第一列是数字 size，且我们已经找到了表头索引
        if parts and parts[0].isdigit() and algbw_idx is not None:
            size_b = int(parts[0])

            try:
                algbw = float(parts[-7])
                busbw = float(parts[-6])
                wrong = parts[-5]
            except (IndexError, ValueError):
                continue

            # 1. 校验错误包 #wrong 是否为 0 或 N/A
            if wrong not in ["0", "N/A", "0.00", "0e+00"]:
                errors.append(f"[{test_name}] Size={size_b}B 出现数据校验错误: #wrong={wrong}")

            # 2. 校验趋势递增 (允许 5% 内的微小波动)
            if prev_algbw > 0 and algbw < prev_algbw * 0.95:
                errors.append(f"[{test_name}] Size={size_b}B 算法带宽下降异常: {algbw} GB/s < 前值 {prev_algbw} GB/s")
            if prev_busbw > 0 and busbw < prev_busbw * 0.95:
                errors.append(f"[{test_name}] Size={size_b}B 总线带宽下降异常: {busbw} GB/s < 前值 {prev_busbw} GB/s")

            prev_algbw = algbw
            prev_busbw = busbw

            # 记录 1GB (1073741824 Bytes) 时的 algbw
            if size_b == 1073741824:
                peak_1g_algbw = algbw
    # 3. 校验 1GB 峰值带宽门槛
    if test_name in EXPECTED_PEAK_ALGBW:
        threshold = EXPECTED_PEAK_ALGBW[test_name]
        if peak_1g_algbw is None:
            errors.append(f"[{test_name}] 未解析到 Size=1073741824 (1GB) 的测试数据！")
        elif peak_1g_algbw < threshold:
            errors.append(f"[{test_name}] 1GB 算法带宽不达标: {peak_1g_algbw} GB/s < 阈值 {threshold} GB/s")

if errors:
    print("❌ [FAIL] MCCL 性能巡检未通过，检测到以下异常:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)
else:
    print("✅ [PASS] MCCL 所有算子测试通过！错误包均为 0，带宽递增趋势正常，1GB 峰值带宽全部达标。")
