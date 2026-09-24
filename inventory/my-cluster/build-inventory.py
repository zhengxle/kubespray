#!/usr/bin/env python3
import os
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 build-inventory.py <IP1> <IP2> ... <IPN>")
        print("Example: python3 build-inventory.py 172.17.0.1 172.17.0.2 ...")
        sys.exit(1)

    all_ips = sys.argv[1:]
    total_count = len(all_ips)

    # --- 1. 节点数量配置 (可通过环境变量动态修改) ---
    master_count = int(os.environ.get('MASTER_COUNT', 3))  # 默认前 3 个 IP 作为 Master
    etcd_count = int(os.environ.get('ETCD_COUNT', 3))      # 默认接下来的 3 个 IP 作为 ETCD

    # --- 2. 各角色凭证配置 ---
    master_user = os.environ.get('MASTER_USER', 'ubuntu')
    master_pass = os.environ.get('MASTER_PASS', 'Master@123.')

    etcd_user = os.environ.get('ETCD_USER', 'ubuntu')
    etcd_pass = os.environ.get('ETCD_PASS', 'Etcd@123.')

    worker_user = os.environ.get('WORKER_USER', 'ubuntu')
    worker_pass = os.environ.get('WORKER_PASS', 'Server@123.')

    # --- 3. 按“先 Master、再 ETCD、后 Worker”的顺序切分 IP ---
    needed_mgmt_ips = master_count + etcd_count

    if total_count <= needed_mgmt_ips:
        print(f"[!] 警告: 传入 IP 总数 ({total_count}) 小于或等于管理节点总需求 ({needed_mgmt_ips})。将自动降级复用节点。")
        master_ips = all_ips[:master_count]
        etcd_ips = all_ips[:etcd_count]
        worker_ips = all_ips
    else:
        # 完全独立切分
        master_ips = all_ips[:master_count]
        etcd_ips = all_ips[master_count : master_count + etcd_count]
        worker_ips = all_ips[master_count + etcd_count :]

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

    # 第一步：写入 Master 节点信息
    for i, ip in enumerate(master_ips, start=1):
        lines.append(f"    master{i}:")
        lines.append(f"      ansible_host: {ip}")
        lines.append(f"      ip: {ip}")
        lines.append(f"      access_ip: {ip}")
        lines.append(f"      ansible_user: {master_user}")
        lines.append(f"      ansible_password: '{master_pass}'")
        lines.append(f"      ansible_become_password: '{master_pass}'")

    # 第二步：写入 ETCD 节点信息
    for i, ip in enumerate(etcd_ips, start=1):
        lines.append(f"    etcd{i}:")
        lines.append(f"      ansible_host: {ip}")
        lines.append(f"      ip: {ip}")
        lines.append(f"      access_ip: {ip}")
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
    print(f"    1. Master 节点 ({len(master_ips)}台) : master1 ~ master{len(master_ips)} ({', '.join(master_ips)})")
    print(f"    2. ETCD 节点   ({len(etcd_ips)}台)   : etcd1 ~ etcd{len(etcd_ips)} ({', '.join(etcd_ips)})")
    print(f"    3. Worker 节点 ({len(worker_ips)}台) : node1 ~ node{len(worker_ips)} (纯计算节点)")

if __name__ == "__main__":
    main()
