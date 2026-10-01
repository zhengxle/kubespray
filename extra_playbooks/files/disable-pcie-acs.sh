#!/bin/bash
for BDF in $(lspci -d "*:*:*" | awk '{print $1}'); do
	# 跳过不支持 ACS 的 PCIe 设备
	setpci -v -s "${BDF}" ECAP_ACS+0x6.w >/dev/null 2>&1
	if [ $? -ne 0 ]; then
		continue
	fi
	# 关闭 ACS Control
	setpci -v -s "${BDF}" ECAP_ACS+0x6.w=0000
done
