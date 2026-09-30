#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# ==========================================================
# 模块名 @ Version:
#        @ Author: xiaolerzheng(zxl), xiaolerzheng@gmail.com
#        @ license: LGPL
#        @ Copyright (C) org |YEAR|
# =========================================================
import csv
import os
import hashlib
import ipaddress  # 导入用于计算 /16 网段的标准库
import sys

# ============ 物理网口定义 ============
BOND_COMPUTE_1 = ("bond_compute0", ["ens55f0np0", "ens55f1np1"])    # PCI 3d:00
BOND_COMPUTE_2 = ("bond_compute1", ["ens50f0np0", "ens50f1np1"])    # PCI 29:00
BOND_COMPUTE_3 = ("bond_compute2", ["enp96s0f0np0", "enp96s0f1np1"])  # PCI 60:00
BOND_COMPUTE_4 = ("bond_compute3", ["enp75s0f0np0", "enp75s0f1np1"])  # PCI 4b:00

BOND_STORAGE = ("bond_storage0", ["ens1f0np0", "ens1f1np1"])
BOND_BUSINESS = ("bond0", ["enp184s0f0", "enp184s0f1"])

# ============ 每类网络的 Bond 参数 ============
BUSINESS_MODE = "802.3ad"
BUSINESS_MII = 100
BUSINESS_LACP_RATE = "fast"
BUSINESS_HASH_POLICY = "layer3+4"

COMPUTE_MODE = "802.3ad"
COMPUTE_MII = 100
COMPUTE_LACP_RATE = "fast"
COMPUTE_HASH_POLICY = "layer3+4"
COMPUTE_GRATUITOUS_ARP = 5

STORAGE_MODE = "802.3ad"
STORAGE_MII = 100
STORAGE_LACP_RATE = "fast"
STORAGE_HASH_POLICY = "layer3+4"
STORAGE_GRATUITOUS_ARP = 5

MTU_BUSINESS = None
MTU_STORAGE = 8000
MTU_COMPUTE = 8000

NIC_TYPE_BUSINESS = 0x00
NIC_TYPE_COMPUTE = 0x01
NIC_TYPE_STORAGE = 0x02

# ============ 计算网路由表 ID 与优先级 ============
COMPUTE_ROUTE_TABLES = [201, 202, 203, 204]
COMPUTE_RULE_PRIORITY_BASE = 100


def make_bond_mac(biz_ip, nic_type, suffix=0):
    """基于 Business_IP + 网卡类型 + 序号 生成唯一的 MAC 地址"""
    if not biz_ip:
        return None
    key = f"{biz_ip}-{nic_type}-{suffix}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest().upper()
    h = [digest[i:i + 2] for i in range(0, 8, 2)]
    return "02:{:02X}:{}:{}:{}:{}".format(nic_type & 0xFF, h[0], h[1], h[2], h[3])


def render_ethernets(members, mtu):
    lines = []
    for m in members:
        lines.extend([
            f"    {m}:",
            "      dhcp4: false",
            "      dhcp6: false",
        ])
    return lines


def render_bond(bond_name, members, addresses, mtu,
                mode, mii,
                lacp_rate=None, hash_policy=None, gratuitous_arp=None,
                gateway=None, nameservers=None, mac_address=None,
                routes=None, routing_policy=None):
    lines = [
        f"    {bond_name}:",
        "      interfaces:",
    ]
    for m in members:
        lines.append(f"        - {m}")
    if mac_address:
        lines.append(f"      macaddress: {mac_address}")
    lines.append("      addresses:")
    for addr in addresses:
        lines.append(f"        - {addr}")
    if mtu is not None:
        lines.append(f"      mtu: {mtu}")
    lines.extend([
        "      parameters:",
        f"        mode: {mode}",
        f"        mii-monitor-interval: {mii}",
    ])
    if mode == "802.3ad":
        if lacp_rate:
            lines.append(f"        lacp-rate: {lacp_rate}")
        if hash_policy:
            lines.append(f"        transmit-hash-policy: {hash_policy}")

    # 支持在所有模式下生成 gratuitous-arp
    if gratuitous_arp is not None:
        lines.append(f"        gratuitous-arp: {gratuitous_arp}")

    if routes:
        lines.append("      routes:")
        for r in routes:
            lines.append(f"        - to: {r['to']}")
            if r.get("via"):
                lines.append(f"          via: {r['via']}")
            if r.get("table") is not None:
                lines.append(f"          table: {r['table']}")
            if r.get("on-link") is not None:
                lines.append(f"          on-link: {str(r['on-link']).lower()}")
            if r.get("metric") is not None:
                lines.append(f"          metric: {r['metric']}")
    elif gateway:
        lines.extend([
            "      routes:",
            "        - to: default",
            f"          via: {gateway}",
        ])

    if routing_policy:
        lines.append("      routing-policy:")
        for p in routing_policy:
            lines.append(f"        - from: {p['from']}")
            lines.append(f"          table: {p['table']}")
            if p.get("priority") is not None:
                lines.append(f"          priority: {p['priority']}")

    if nameservers:
        lines.extend([
            "      nameservers:",
            "        addresses: [" + ", ".join(nameservers) + "]",
        ])
    return lines


def write_file(output_dir, filename, lines):
    config_file = os.path.join(output_dir, filename)
    with open(config_file, 'w', encoding='utf-8') as out_f:
        out_f.write("\n".join(lines) + "\n")


def generate_netplan_configs(csv_file, output_dir="./netplan_configs"):
    os.makedirs(output_dir, exist_ok=True)

    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = {k.strip(): (v.strip() if v else '') for k, v in raw_row.items() if k}
            sn = row.get('SN', '')
            hostname = row.get('Hostname', '')
            biz_ip = row.get('Business_IP', '')
            biz_gw = row.get('Business_Gateway', '')
            storage_ip = row.get('Storage_IP', '')

            # 若未配置 Business_IP 则无法生成对应的配置文件
            if not biz_ip:
                print(f"[警告] 跳过 Hostname={hostname}, SN={sn}：缺少 Business_IP")
                continue

            header = [
                "# Auto-generated by Deployment Tool",
                f"# Hostname: {hostname} | SN: {sn} | Biz_IP: {biz_ip}",
                "network:",
                "  version: 2",
                "  renderer: networkd",
                "  ethernets:",
            ]

            # ---------- 01-business ----------
            bond_name, members = BOND_BUSINESS
            mac = make_bond_mac(biz_ip, NIC_TYPE_BUSINESS)
            lines = list(header)
            lines += render_ethernets(members, MTU_BUSINESS)
            lines.append("  bonds:")
            lines += render_bond(
                bond_name, members,
                addresses=[f"{biz_ip}/24"],
                mtu=MTU_BUSINESS,
                mode=BUSINESS_MODE,
                mii=BUSINESS_MII,
                lacp_rate=BUSINESS_LACP_RATE,
                hash_policy=BUSINESS_HASH_POLICY,
                gateway=biz_gw,
                nameservers=["172.16.5.4", "114.114.114.114", "8.8.8.8"],
                mac_address=mac,
            )
            # 文件名改为以 biz_ip 命名
            write_file(output_dir, f"01-business-{biz_ip}.yaml", lines)

            # ---------- 02-compute（策略路由） ----------
            param_ips = [
                row.get(k) for k in
                ['Param_IP_1', 'Param_IP_2', 'Param_IP_3', 'Param_IP_4']
                if row.get(k)
            ]
            if param_ips:
                all_compute_members = []
                for _, members in [BOND_COMPUTE_1, BOND_COMPUTE_2,
                                   BOND_COMPUTE_3, BOND_COMPUTE_4]:
                    all_compute_members += members

                lines = list(header)
                lines += render_ethernets(all_compute_members, MTU_COMPUTE)
                lines.append("  bonds:")

                for idx, (bond_name, members) in enumerate(
                        [BOND_COMPUTE_1, BOND_COMPUTE_2,
                         BOND_COMPUTE_3, BOND_COMPUTE_4]):
                    if idx >= len(param_ips):
                        break

                    ip_str = param_ips[idx]
                    mac = make_bond_mac(biz_ip, NIC_TYPE_COMPUTE, suffix=idx)
                    ip_cidr = f"{ip_str}/24"
                    table_id = COMPUTE_ROUTE_TABLES[idx]

                    # 1. 自动计算 IP 对应的 /16 网段
                    interface = ipaddress.ip_interface(f"{ip_str}/16")
                    network_16 = str(interface.network)

                    # 2. 网关推导为同网段的 .254
                    ip_prefix = ".".join(ip_str.split(".")[:3])
                    compute_gw = f"{ip_prefix}.254"

                    routes = [
                        {
                            "to": network_16,
                            "via": compute_gw,
                            "table": table_id
                        }
                    ]
                    routing_policy = [
                        {
                            "from": ip_str,
                            "table": table_id,
                            "priority": COMPUTE_RULE_PRIORITY_BASE + idx
                        }
                    ]

                    lines += render_bond(
                        bond_name, members,
                        addresses=[ip_cidr],
                        mtu=MTU_COMPUTE,
                        mode=COMPUTE_MODE,
                        mii=COMPUTE_MII,
                        lacp_rate=COMPUTE_LACP_RATE,
                        hash_policy=COMPUTE_HASH_POLICY,
                        gratuitous_arp=COMPUTE_GRATUITOUS_ARP,
                        mac_address=mac,
                        routes=routes,
                        routing_policy=routing_policy,
                    )
                # 文件名改为以 biz_ip 命名
                write_file(output_dir, f"02-compute-{biz_ip}.yaml", lines)

            # ---------- 03-storage（目的静态路由） ----------
            if storage_ip:
                bond_name, members = BOND_STORAGE
                mac = make_bond_mac(biz_ip, NIC_TYPE_STORAGE)
                lines = list(header)
                lines += render_ethernets(members, MTU_STORAGE)
                lines.append("  bonds:")

                # 1. 计算存储网对应的目的 /16 网段
                interface = ipaddress.ip_interface(f"{storage_ip}/16")
                storage_network_16 = str(interface.network)

                # 2. 推导存储网网关（.254）
                storage_prefix = ".".join(storage_ip.split(".")[:3])
                storage_gw = f"{storage_prefix}.254"

                # 3. 配置标准的目的路由
                storage_routes = [
                    {
                        "to": storage_network_16,
                        "via": storage_gw
                    }
                ]

                lines += render_bond(
                    bond_name, members,
                    addresses=[f"{storage_ip}/24"],
                    mtu=MTU_STORAGE,
                    mode=STORAGE_MODE,
                    mii=STORAGE_MII,
                    lacp_rate=STORAGE_LACP_RATE,
                    hash_policy=STORAGE_HASH_POLICY,
                    gratuitous_arp=STORAGE_GRATUITOUS_ARP,
                    mac_address=mac,
                    routes=storage_routes,
                )
                # 文件名改为以 biz_ip 命名
                write_file(output_dir, f"03-storage-{biz_ip}.yaml", lines)


if __name__ == "__main__":
    csv_filename = sys.argv[1] if len(sys.argv) > 1 else 'server_sn_ip.csv'
    generate_netplan_configs(csv_filename)
