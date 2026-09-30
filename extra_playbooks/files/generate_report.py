#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import glob
from datetime import datetime

LOG_DIR = os.environ.get("LOG_DIR", "./rdma_rail_logs")

# ANSI 颜色定义
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def parse_bw_from_log(log_path):
    """从 ib_write_bw 日志提取平均带宽 (Gb/sec)"""
    if not os.path.exists(log_path):
        return 0.0

    bw_gbps = 0.0
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

        lines = content.strip().split('\n')
        for line in reversed(lines):
            line_str = line.strip()
            if re.match(r'^\d+\s+\d+', line_str):
                parts = line_str.split()
                if len(parts) >= 4:
                    try:
                        val = float(parts[-2])
                        if "MiB/sec" in content or "MB/sec" in content:
                            bw_gbps = val * 8 * 1.048576 / 1000.0
                        else:
                            bw_gbps = val
                        break
                    except ValueError:
                        continue

        if bw_gbps == 0.0:
            match = re.search(r'(\d+\.\d+)\s+Gb/sec', content)
            if match:
                bw_gbps = float(match.group(1))

    return bw_gbps

def format_node_name(node_id):
    """格式化节点名称为 gpu-node-XXX"""
    if str(node_id).isdigit():
        return f"gpu-node-{int(node_id):03d}"
    return str(node_id)

def main():
    log_files = glob.glob(os.path.join(LOG_DIR, "client_rail*.log"))
    if not log_files:
        print(f"错误: 目录 '{LOG_DIR}' 下未查找到任何 client_rail*.log 测试日志！")
        sys.exit(1)

    # 1. 自动扫描日志目录，找出所有测试过的 (client_node, server_node) 组合
    pairs_data = {}  # key: (client_id, server_id, qp), value: {rail0: bw, ..., rail4: bw}

    for f in log_files:
        fname = os.path.basename(f)
        # 匹配日志文件名中的 rail ID 以及 Client/Server 节点标识 (IP 尾数)
        match = re.search(r'client_rail(\d+)_\d+\.\d+\.\d+\.(\d+)_to_\d+\.\d+\.\d+\.(\d+)_q(\d+)\.log', fname)
        if match:
            rail_id = int(match.group(1))
            client_id = match.group(2)
            server_id = match.group(3)
            qp = match.group(4)

            pair_key = (client_id, server_id, qp)
            if pair_key not in pairs_data:
                pairs_data[pair_key] = {}

            bw = parse_bw_from_log(f)
            pairs_data[pair_key][rail_id] = bw

    if not pairs_data:
        print("未能在日志文件名中解析出有效的节点信息。")
        sys.exit(1)

    # 2. 打印表头（包含 Rail 0 ~ Rail 4 存储网）
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    width = 132
    print("=" * width)
    print(f"{'RDMA 5-Rail (4 Compute + 1 Storage) 节点间带宽测试汇总报告 (' + now_str + ')':^{width}}")
    print("=" * width)
    print(f"{'Client Node':<15} {'Server Node':<15} {'QP':<4} {'Rail 0 (Gbps)':<15} {'Rail 1 (Gbps)':<15} {'Rail 2 (Gbps)':<15} {'Rail 3 (Gbps)':<15} {'Rail 4 (Gbps)':<15} {'Total (Gbps)':<12}")
    print("-" * width)

    # 3. 按节点自然排序输出（支持 node1~node49 动态扩展）
    sorted_keys = sorted(
        pairs_data.keys(),
        key=lambda x: (int(x[0]) if x[0].isdigit() else x[0], int(x[1]) if x[1].isdigit() else x[1])
    )

    for client_id, server_id, qp in sorted_keys:
        client_name = format_node_name(client_id)
        server_name = format_node_name(server_id)
        rails = pairs_data[(client_id, server_id, qp)]

        r0 = rails.get(0, 0.0)
        r1 = rails.get(1, 0.0)
        r2 = rails.get(2, 0.0)
        r3 = rails.get(3, 0.0)
        r4 = rails.get(4, 0.0)  # 存储网 Rail 4
        total = r0 + r1 + r2 + r3 + r4

        # 配色逻辑：5 条 Rail 均正常满速 (例: 约 >= 900 Gbps) 为绿色，全断为红色，部分异常为黄色
        if total >= 880.0:
            color = GREEN
        elif total == 0.0:
            color = RED
        else:
            color = YELLOW

        row_str = f"{client_name:<15} {server_name:<15} {qp:<4} {r0:<15.2f} {r1:<15.2f} {r2:<15.2f} {r3:<15.2f} {r4:<15.2f} {total:<12.2f}"
        print(f"{color}{row_str}{RESET}")

    print("=" * width)

if __name__ == "__main__":
    main()
