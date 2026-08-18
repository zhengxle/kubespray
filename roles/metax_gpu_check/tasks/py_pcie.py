import sys, re

raw_text = """
  KMD                                  3.9.6
  VBIOS                                1.35.2.0
  NUMA NODE                            0
  CURRENT PCIE                         speed: 2.5 GT/s  width: x16
  MAXIMUM PCIE                         speed: 32.0 GT/s  width: x16
  METAXLINK PORTS                      4,5,6
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  GPU ID                               4
  MODEL                                MetaX C500
  BDF                                  0000:32:00.0
  KMD                                  3.9.6
  VBIOS                                1.35.2.0
  NUMA NODE                            0
  CURRENT PCIE                         speed: 2.5 GT/s  width: x16
  MAXIMUM PCIE                         speed: 32.0 GT/s  width: x16
  METAXLINK PORTS                      4,5,6
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  GPU ID                               5
  MODEL                                MetaX C500
  BDF                                  0000:38:00.0
  KMD                                  3.9.6
  VBIOS                                1.35.2.0
  NUMA NODE                            0
  CURRENT PCIE                         speed: 2.5 GT/s  width: x16
  MAXIMUM PCIE                         speed: 32.0 GT/s  width: x16
  METAXLINK PORTS                      4,5,6
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  GPU ID                               6
  MODEL                                MetaX C500
  BDF                                  0000:3b:00.0
  KMD                                  3.9.6
  VBIOS                                1.35.2.0
  NUMA NODE                            0
  CURRENT PCIE                         speed: 2.5 GT/s  width: x16
  MAXIMUM PCIE                         speed: 32.0 GT/s  width: x16
  METAXLINK PORTS                      4,5,6
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  GPU ID                               7
  MODEL                                MetaX C500
  BDF                                  0000:3c:00.0
  KMD                                  3.9.6
  VBIOS                                1.35.2.0
  NUMA NODE                            0
  CURRENT PCIE                         speed: 2.5 GT/s  width: x16
  MAXIMUM PCIE                         speed: 32.0 GT/s  width: x16
  METAXLINK PORTS                      4,5,6
 ──────────────────────────────────────────────────────────────────────────────────────────────────
                                   PCIE UNIDIRECTIONAL BENCHMARK

  SRC             DST                          EFFECTIVE           RAW   TRANSMISSION         DATA
  DEVICE          DEVICE           SIZE(B)     BANDWIDTH     BANDWIDTH   DELAY   (us)   VALIDATION
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  CPU       <<    BOARD#0       7516192768    56.84 GB/s    63.58 GB/s      132238.87         PASS
  CPU       <<    BOARD#1       7516192768    56.84 GB/s    63.58 GB/s      132224.91         PASS
  CPU       <<    BOARD#2       7516192768    56.85 GB/s    63.59 GB/s      132220.26         PASS
  CPU       <<    BOARD#3       7516192768    56.85 GB/s    63.59 GB/s      132215.61         PASS
  CPU       <<    BOARD#4       7516192768    56.85 GB/s    63.59 GB/s      132217.93         PASS
  CPU       <<    BOARD#5       7516192768    56.84 GB/s    63.58 GB/s      132227.24         PASS
  CPU       <<    BOARD#6       7516192768    56.84 GB/s    63.58 GB/s      132227.24         PASS
  CPU       <<    BOARD#7       7516192768    56.85 GB/s    63.59 GB/s      132220.26         PASS
"""
clean_lines = []
for line in raw_text.splitlines():
    if "\r" in line:
        clean_lines.append(line.split("\r")[-1])
    else:
        clean_lines.append(line)

full_output = "\n".join(clean_lines)
print("=== 完整测试输出 ===")
print(full_output)
print("====================")

# 2. 设置带宽阈值 (GB/s)
BANDWIDTH_THRESHOLD = 55.0  # MetaX Link 预期 > 45 GB/s

failed_links = []
total_links = 0

# 正则匹配数据行: GPU#0  GPU#1  metaxlink/pcie  SIZE  EFFECTIVE_BW  ...
pattern = re.compile(r"(\w+)\s+<<\s+BOARD#(\d+)\s+\d+\s+([\d\.]+)\s+GB/s\s+([\d\.]+)\s+GB/s")

for line in clean_lines:
    match = pattern.search(line)
    if match:
        print(match.groups())
        src, dst, eff_bw, raw_bw = match.groups()
        eff_bw = float(eff_bw)
        raw_bw = float(raw_bw)
        total_links += 1

        # 根据拓扑类型校验带宽阈值
        if eff_bw < BANDWIDTH_THRESHOLD:
            failed_links.append(f"GPU#{src} -> GPU#{dst}: {eff_bw} GB/s < 阈值 {BANDWIDTH_THRESHOLD} GB/s")

if total_links == 0:
    print("❌ [FAIL] 未能正确解析到任何 P2P 传输链路数据！")
    sys.exit(1)
if failed_links:
    print(f"❌ [FAIL] 检测到 {len(failed_links)} 条链路带宽未达标:")
    for err in failed_links:
        print(f"  - {err}")
    sys.exit(1)
else:
    print(f"✅ [PASS] 所有 {total_links} 条 P2P 链路带宽校验通过！")

