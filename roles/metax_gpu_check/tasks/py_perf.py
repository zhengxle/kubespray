import sys, re

raw_text = """"
                                           MXVS P2P TEST

                                                 EFFECTIVE          RAW    TRANSMISSION        DATA
 DEVICE1   DEVICE2   TOPOLOGY    SIZE(B)         BANDWIDTH    BANDWIDTH    DELAY   (us)  VALIDATION
 ──────────────────────────────────────────────────────────────────────────────────────────────────
 GPU#0     GPU#1     metaxlink   7516192768     50.74 GB/s   63.58 GB/s       137958.24        PASS
 GPU#0     GPU#2     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139893.22        PASS
 GPU#0     GPU#3     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139893.68        PASS
 GPU#0     GPU#4     pcie        7516192768     37.72 GB/s   46.11 GB/s       185592.20        PASS
 GPU#0     GPU#5     pcie        7516192768     37.72 GB/s   46.11 GB/s       185593.20        PASS
 GPU#0     GPU#6     pcie        7516192768     37.72 GB/s   46.11 GB/s       185592.45        PASS
 GPU#0     GPU#7     pcie        7516192768     37.72 GB/s   46.11 GB/s       185592.26        PASS
 GPU#1     GPU#0     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139892.49        PASS
 GPU#1     GPU#2     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139893.33        PASS
 GPU#1     GPU#3     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139892.72        PASS
 GPU#1     GPU#4     pcie        7516192768     37.72 GB/s   46.11 GB/s       185595.13        PASS
 GPU#1     GPU#5     pcie        7516192768     37.72 GB/s   46.11 GB/s       185594.08        PASS
 GPU#1     GPU#6     pcie        7516192768     37.72 GB/s   46.11 GB/s       185593.61        PASS
 GPU#1     GPU#7     pcie        7516192768     37.72 GB/s   46.11 GB/s       185594.12        PASS
 GPU#2     GPU#0     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139894.67        PASS
 GPU#2     GPU#1     metaxlink   7516192768     50.76 GB/s   63.61 GB/s       137911.79        PASS
 GPU#2     GPU#3     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139893.59        PASS
 GPU#2     GPU#4     pcie        7516192768     37.72 GB/s   46.11 GB/s       185593.46        PASS
 GPU#2     GPU#5     pcie        7516192768     37.72 GB/s   46.11 GB/s       185593.91        PASS
 GPU#2     GPU#6     pcie        7516192768     37.72 GB/s   46.11 GB/s       185594.60        PASS
 GPU#2     GPU#7     pcie        7516192768     37.72 GB/s   46.11 GB/s       185593.57        PASS
 GPU#3     GPU#0     metaxlink   7516192768     50.05 GB/s   62.72 GB/s       139864.89        PASS
 GPU#3     GPU#1     metaxlink   7516192768     50.76 GB/s   63.60 GB/s       137914.03        PASS
 GPU#3     GPU#2     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139893.77        PASS
 GPU#3     GPU#4     pcie        7516192768     37.72 GB/s   46.11 GB/s       185597.83        PASS
 GPU#3     GPU#5     pcie        7516192768     37.72 GB/s   46.11 GB/s       185597.08        PASS
 GPU#3     GPU#6     pcie        7516192768     37.72 GB/s   46.11 GB/s       185597.03        PASS
 GPU#3     GPU#7     pcie        7516192768     37.72 GB/s   46.11 GB/s       185596.65        PASS
 GPU#4     GPU#0     pcie        7516192768     37.72 GB/s   46.12 GB/s       185556.92        PASS
 GPU#4     GPU#1     pcie        7516192768     37.72 GB/s   46.12 GB/s       185557.59        PASS
 GPU#4     GPU#2     pcie        7516192768     37.72 GB/s   46.12 GB/s       185557.67        PASS
 GPU#4     GPU#3     pcie        7516192768     37.72 GB/s   46.12 GB/s       185556.47        PASS
 GPU#4     GPU#5     metaxlink   7516192768     50.05 GB/s   62.72 GB/s       139864.01        PASS
 GPU#4     GPU#6     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139894.02        PASS
 GPU#4     GPU#7     metaxlink   7516192768     50.05 GB/s   62.72 GB/s       139866.02        PASS
 GPU#5     GPU#0     pcie        7516192768     37.72 GB/s   46.12 GB/s       185557.07        PASS
 GPU#5     GPU#1     pcie        7516192768     37.72 GB/s   46.12 GB/s       185557.76        PASS
 GPU#5     GPU#2     pcie        7516192768     37.72 GB/s   46.12 GB/s       185556.98        PASS
 GPU#5     GPU#3     pcie        7516192768     37.72 GB/s   46.12 GB/s       185557.41        PASS
 GPU#5     GPU#4     metaxlink   7516192768     50.75 GB/s   63.60 GB/s       137917.69        PASS
 GPU#5     GPU#6     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139894.24        PASS
 GPU#5     GPU#7     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139893.59        PASS
 GPU#6     GPU#0     pcie        7516192768     37.72 GB/s   46.12 GB/s       185556.22        PASS
 GPU#6     GPU#1     pcie        7516192768     37.72 GB/s   46.12 GB/s       185556.54        PASS
 GPU#6     GPU#2     pcie        7516192768     37.72 GB/s   46.12 GB/s       185556.94        PASS
 GPU#6     GPU#3     pcie        7516192768     37.72 GB/s   46.12 GB/s       185558.23        PASS
 GPU#6     GPU#4     metaxlink   7516192768     50.74 GB/s   63.58 GB/s       137958.05        PASS
 GPU#6     GPU#5     metaxlink   7516192768     50.05 GB/s   62.72 GB/s       139864.98        PASS
 GPU#6     GPU#7     metaxlink   7516192768     50.05 GB/s   62.72 GB/s       139865.83        PASS
 GPU#7     GPU#0     pcie        7516192768     37.72 GB/s   46.12 GB/s       185558.91        PASS
 GPU#7     GPU#1     pcie        7516192768     37.72 GB/s   46.12 GB/s       185558.65        PASS
 GPU#7     GPU#2     pcie        7516192768     37.72 GB/s   46.12 GB/s       185558.81        PASS
 GPU#7     GPU#3     pcie        7516192768     37.72 GB/s   46.12 GB/s       185559.08        PASS
 GPU#7     GPU#4     metaxlink   7516192768     50.74 GB/s   63.58 GB/s       137960.04        PASS
 GPU#7     GPU#5     metaxlink   7516192768     50.05 GB/s   62.72 GB/s       139865.88        PASS
 GPU#7     GPU#6     metaxlink   7516192768     50.04 GB/s   62.70 GB/s       139894.62        PASS
"""
lines = raw_text.splitlines()

pattern = re.compile(
	r"^\s*GPU#(\d+)\s+GPU#(\d+)\s+([a-zA-Z0-9_]+)\s+(\d+)\s+([\d\.]+)\s+GB/s\s+([\d\.]+)\s+GB/s\s+([\d\.]+)\s+(\w+)"
)

metaxlink_count = 0
pcie_count = 0

for line in lines:
	match = pattern.match(line)
	if match:
		src, dst, topo, size, eff_bw, raw_bw, delay, status = match.groups()
		raw_bw_val = float(raw_bw)
		src_id, dst_id = int(src), int(dst)

		if status != "PASS":
			print(f"FAIL: GPU#{src} -> GPU#{dst} 验证状态异常: {status}")
			sys.exit(1)

		if (src_id < 4 and dst_id < 4) or (src_id >= 4 and dst_id >= 4):
			if topo != "metaxlink":
				print(f"FAIL: GPU#{src} -> GPU#{dst} 预期为 metaxlink，实际为 {topo}")
				sys.exit(1)
			if raw_bw_val < 60.0:
				print(f"FAIL: GPU#{src} -> GPU#{dst} MetaX Link 带宽低 ({raw_bw_val} GB/s < 60.0 GB/s)")
				sys.exit(1)
			metaxlink_count += 1
		else:
			if topo != "pcie":
				print(f"FAIL: GPU#{src} -> GPU#{dst} 预期为 pcie，实际为 {topo}")
				sys.exit(1)
			if raw_bw_val < 40.0:
				print(f"FAIL: GPU#{src} -> GPU#{dst} PCIe 带宽低 ({raw_bw_val} GB/s < 40.0 GB/s)")
				sys.exit(1)
			pcie_count += 1

if metaxlink_count != 24 or pcie_count != 32:
	print(f"FAIL: P2P 测试链路数量不完整 (metaxlink: {metaxlink_count}/24, pcie: {pcie_count}/32)")
	sys.exit(1)
print(metaxlink_count, pcie_count)
