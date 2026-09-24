#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from pathlib import Path
from openpyxl import Workbook

LOG_FILE = Path("sn.log")
OUT_FILE = Path("gpu_sn.xlsx")

# 匹配：node1 | CHANGED | rc=0 >>
node_re = re.compile(r'^(\S+)\s+\|\s+CHANGED\s+\|\s+rc=0\s+>>')

# 匹配：GPU#0  MXC500  0000:2c:00.0
gpu_re = re.compile(r'^GPU#(\d+)\b')

# 匹配：pcba serial number : AENA2514000033
sn_re = re.compile(r'pcba serial number\s*:\s*(\S+)')


def node_sort_key(node: str):
    """让 node1、node2、node10 按数字顺序排，而不是按字符串排。"""
    m = re.search(r'(\d+)$', node)
    if m:
        return (0, int(m.group(1)))
    return (1, node)


def main():
    rows = []
    current_node = None
    current_gpu = None

    with LOG_FILE.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # 遇到新节点
            m = node_re.match(line)
            if m:
                current_node = m.group(1)
                current_gpu = None
                continue

            if current_node is None:
                continue

            # 遇到 GPU#N
            m = gpu_re.match(line)
            if m:
                current_gpu = int(m.group(1))
                continue

            # 遇到 pcba serial number
            m = sn_re.search(line)
            if m and current_gpu is not None:
                sn = m.group(1).strip()
                rows.append((current_node, current_gpu, sn))
                current_gpu = None

    # 同一 node + gpu 去重，保留最后一次
    uniq = {}
    for node, gpu, sn in rows:
        uniq[(node, gpu)] = sn

    result = [(node, gpu, sn) for (node, gpu), sn in uniq.items()]
    result.sort(key=lambda x: (node_sort_key(x[0]), x[1]))

    # 写入 Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "gpu_sn"

    # 如果你不想要表头，把这行注释掉即可
    ws.append(["node", "sn"])

    for node, gpu, sn in result:
        ws.append([node, sn])

    wb.save(OUT_FILE)

    print(f"已生成: {OUT_FILE.resolve()}")
    print(f"节点数: {len(set(x[0] for x in result))}, SN 行数: {len(result)}")

    if len(result) != 256:
        print("警告: 期望 32 台 * 8 卡 = 256 行，请检查 sn.log 是否完整。")

    print("前 16 行预览:")
    for node, gpu, sn in result[:16]:
        print(f"{node}\t{sn}")


if __name__ == "__main__":
    main()
