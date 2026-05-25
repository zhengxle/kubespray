#!/usr/bin/env python3
import os
import sys

def scale_rules(node_count):
    if node_count == 1:
        return 1, 1
    elif node_count == 2:
        return 1, 2
    elif node_count == 3:
        return 3, 3
    else:
        return 3, 3

def main():
    ips = sys.argv[1:]
    if not ips:
        print("Usage: inventory.py <IP1> <IP2> ...")
        sys.exit(1)

    config_file = os.environ.get('CONFIG_FILE', './hosts.yml')
    config_dir = os.path.dirname(config_file)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)

    node_count = len(ips)
    master_count, etcd_count = scale_rules(node_count)

    # 1. 采用流式字符串构建，精确控制每一行的输出顺序与缩进
    lines = []
    
    # --- children 区域 ---
    lines.append("all:")
    lines.append("  children:")
    
    lines.append("    calico_rr:")
    lines.append("      hosts: {}")
    
    lines.append("    etcd:")
    lines.append("      hosts:")
    for i in range(1, etcd_count + 1):
        lines.append(f"        node{i}: {{}}")
        
    lines.append("    k8s_cluster:")
    lines.append("      children:")
    lines.append("        kube_control_plane: {}")
    lines.append("        kube_node: {}")
    
    lines.append("    kube_control_plane:")
    lines.append("      hosts:")
    for i in range(1, master_count + 1):
        lines.append(f"        node{i}: {{}}")
        
    lines.append("    kube_node:")
    lines.append("      hosts:")
    for i in range(1, node_count + 1):
        lines.append(f"        node{i}: {{}}")

    # --- hosts 区域 ---
    lines.append("  hosts:")
    for i, ip in enumerate(ips, start=1):
        lines.append(f"    node{i}:")
        # 严格按照你右侧截图的变量顺序输出
        lines.append(f"      ansible_host: {ip}")
        lines.append(f"      ip: {ip}")
        lines.append(f"      access_ip: {ip}")
        lines.append("      ansible_user: metaxadmin")
        lines.append("      ansible_password: '!QAZ2wsx'")
        lines.append("      ansible_become_password: '!QAZ2wsx'")

    # 2. 写入文件
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")

    print(f"--> [Success] Generated strict-ordered inventory at: {config_file}")

if __name__ == "__main__":
    main()
