#!/usr/bin/env python3
import os
import sys
import csv

def read_business_ips(csv_file):
    """从 server_sn_ip.csv 中读取 Business_IP 列，返回有序的 IP 列表。"""
    ips = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 兼容 BOM
        reader = csv.DictReader(f)
        for row in reader:
            ip = (row.get('Business_IP') or '').strip()
            if ip:
                ips.append(ip)
    return ips


def main():
    # --- 0. 确定 CSV 文件路径 (可通过环境变量覆盖) ---
    csv_file = os.environ.get('CSV_FILE', '../../server_sn_ip.csv')
    if not os.path.exists(csv_file):
        print(f"[!] 错误: 找不到 CSV 文件: {csv_file}")
        sys.exit(1)

    # 从 CSV 读取 Business_IP 作为 worker 节点地址
    worker_ips = read_business_ips(csv_file)
    total_count = len(worker_ips)

    if total_count == 0:
        print(f"[!] 错误: CSV 文件 {csv_file} 中未读取到任何 Business_IP。")
        sys.exit(1)

    # --- 1. 节点数量配置 ---
    master_count = int(os.environ.get('MASTER_COUNT', 3))  # Master 节点数量（IP 留空）
    etcd_count = int(os.environ.get('ETCD_COUNT', 3))      # ETCD 节点数量（IP 留空）

    # Master / ETCD 的 IP 先留空（占位）
    master_ips = [''] * master_count
    etcd_ips = [''] * etcd_count

    # --- 2. 各角色凭证配置 ---
    master_user = os.environ.get('MASTER_USER', 'ubuntu')
    master_pass = os.environ.get('MASTER_PASS', 'Master@123.')

    etcd_user = os.environ.get('ETCD_USER', 'ubuntu')
    etcd_pass = os.environ.get('ETCD_PASS', 'Etcd@123.')

    worker_user = os.environ.get('WORKER_USER', 'ubuntu')
    worker_pass = os.environ.get('WORKER_PASS', 'Server@123.')

    config_file = os.environ.get('CONFIG_FILE', './hosts.yml')
    config_dir = os.path.dirname(config_file)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)

    lines = []

    # --- 全局默认凭证 (作用于所有 Worker 节点) ---
    lines.append("all:")
    lines.append("  vars:")
    lines.append(f"    ansible_user: {worker_user}")
    lines.append(f"    ansible_password: '{worker_pass}'")
    lines.append(f"    ansible_become_password: '{worker_pass}'")
    lines.append("  children:")

    lines.append("    calico_rr:")
    lines.append("      hosts: {}")

    # --- 1. ETCD 组拓扑定义 ---
    lines.append("    etcd:")
    lines.append("      hosts:")
    for i in range(1, len(etcd_ips) + 1):
        lines.append(f"        etcd{i}: {{}}")

    lines.append("    k8s_cluster:")
    lines.append("      children:")
    lines.append("        kube_control_plane: {}")
    lines.append("        kube_node: {}")

    # --- 2. Master 组拓扑定义 ---
    lines.append("    kube_control_plane:")
    lines.append("      hosts:")
    for i in range(1, len(master_ips) + 1):
        lines.append(f"        master{i}: {{}}")

    # --- 3. Worker 组拓扑定义 ---
    lines.append("    kube_node:")
    lines.append("      hosts:")
    for i in range(1, len(worker_ips) + 1):
        lines.append(f"        node{i}: {{}}")

    # --- Hosts 节点列表 (按 Master -> ETCD -> Worker 顺序写入) ---
    lines.append("  hosts:")

    # 第一步：写入 Master 节点信息（IP 留空占位）
    for i in range(1, len(master_ips) + 1):
        lines.append(f"    master{i}:")
        lines.append(f"      ansible_host: {master_ips[i-1]}")
        lines.append(f"      ip: {master_ips[i-1]}")
        lines.append(f"      access_ip: {master_ips[i-1]}")
        lines.append(f"      ansible_user: {master_user}")
        lines.append(f"      ansible_password: '{master_pass}'")
        lines.append(f"      ansible_become_password: '{master_pass}'")

    # 第二步：写入 ETCD 节点信息（IP 留空占位）
    for i in range(1, len(etcd_ips) + 1):
        lines.append(f"    etcd{i}:")
        lines.append(f"      ansible_host: {etcd_ips[i-1]}")
        lines.append(f"      ip: {etcd_ips[i-1]}")
        lines.append(f"      access_ip: {etcd_ips[i-1]}")
        lines.append(f"      ansible_user: {etcd_user}")
        lines.append(f"      ansible_password: '{etcd_pass}'")
        lines.append(f"      ansible_become_password: '{etcd_pass}'")

    # 第三步：写入 Worker 节点信息 (继承全局默认凭证)
    for i, ip in enumerate(worker_ips, start=1):
        lines.append(f"    node{i}:")
        lines.append(f"      ansible_host: {ip}")
        lines.append(f"      ip: {ip}")
        lines.append(f"      access_ip: {ip}")

    # 写入文件
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")

    print(f"--> [Success] 成功生成 Kubernetes Inventory 清单: {config_file}")
    print(f"    1. Master 节点 ({len(master_ips)}台) : master1 ~ master{len(master_ips)} (IP 待填写)")
    print(f"    2. ETCD 节点   ({len(etcd_ips)}台)   : etcd1 ~ etcd{len(etcd_ips)} (IP 待填写)")
    print(f"    3. Worker 节点 ({len(worker_ips)}台) : node1 ~ node{len(worker_ips)} (来自 CSV 的 Business_IP)")

if __name__ == "__main__":
    main()
