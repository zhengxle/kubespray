#!/usr/bin/env python3
"""
scan_bntx.py - 博通网卡链路状态、CRC/FEC 误码与 DDM 光诊断综合采集脚本
集成 niccli_optic.py (优先) 与 ethtool (降级兜底)
"""

import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys

NICCLI = os.environ.get("NICCLI") or shutil.which("niccli") or "niccli"
TIMEOUT = 30
KV_RE = re.compile(r"^(.+?)\s+:\s?(.*)$")
CH_RE = re.compile(r"\((?:Chan|Channel)\s*(\d+)\)")

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return res.stdout.strip()
    except Exception:
        return ""

def rd(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None

def num(v):
    m = re.match(r"\s*(-?[\d.]+)", v or "")
    return float(m.group(1)) if m else None

def mw(v):
    m = re.match(r"\s*([\d.]+)\s*mW", v or "")
    return float(m.group(1)) if m else None

def dbm(x):
    return 10 * math.log10(x) if x is not None and x > 0 else float("-inf")

# ---------------------------------------------------------------- niccli DOM 解析
def get_niccli_dom():
    """使用 niccli 批量提取全局博通网卡 DOM 诊断"""
    if not os.path.exists(NICCLI) and not shutil.which("niccli"):
        return {}

    dom_data = {}
    try:
        # 1. 获取网卡序号与 PCI/Dev 映射
        r = subprocess.run([NICCLI, "--list"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return {}
        
        list_re = re.compile(r"^\s*(\d+)\)\s+(\S+)\s+([0-9A-Fa-f:]{17})\s+(\S+)\s+([0-9A-Fa-f]{4}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-7])")
        for line in r.stdout.splitlines():
            m = list_re.match(line)
            if not m:
                continue
            idx, board, mac, fw, pci = m.groups()
            pci = pci.lower()
            nets = sorted(os.path.basename(p) for p in glob.glob(f"/sys/bus/pci/devices/{pci}/net/*"))
            dev = nets[0] if nets else None
            if not dev:
                continue

            # 2. 读取指定网卡的端口 DOM 信息
            cr = subprocess.run([NICCLI, "-i", str(idx), "cable", "-m", "--show"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
            if cr.returncode != 0 or "Identifier" not in cr.stdout:
                continue

            # 3. 解析 KV 数据与通道功率
            kv, tx_map, rx_map, flags = {}, {}, {}, []
            for dline in cr.stdout.splitlines():
                km = KV_RE.match(dline)
                if not km:
                    continue
                k, v = km.group(1).strip(), km.group(2).strip()
                kl = re.sub(r"\s+", " ", k.lower())
                ch = CH_RE.search(k)
                if "alarm" in kl or "warning" in kl:
                    if v.lower() == "on":
                        flags.append(k)
                    continue
                if ch:
                    n = int(ch.group(1))
                    if kl.startswith("transmit") or "output power" in kl:
                        tx_map[n] = mw(v)
                    elif kl.startswith("rcvr") or kl.startswith("receiver"):
                        rx_map[n] = mw(v)
                    continue
                kv[kl] = v

            active_lanes = sorted(set(rx_map) | set(tx_map))
            tx_dbm = [f"{dbm(tx_map[n]):.2f}" if dbm(tx_map.get(n)) > -30 else "N/A" for n in active_lanes]
            rx_dbm = [f"{dbm(rx_map[n]):.2f}" if dbm(rx_map.get(n)) > -30 else "N/A" for n in active_lanes]

            dom_data[dev] = {
                "vendor_pn": kv.get("vendor pn", "N/A"),
                "vendor_sn": kv.get("vendor sn", "N/A"),
                "temp": f"{num(kv.get('module temperature')):.1f} C" if num(kv.get("module temperature")) else "N/A",
                "rx_power": "/".join(rx_dbm) + " dBm" if any(x != "N/A" for x in rx_dbm) else "N/A",
                "tx_power": "/".join(tx_dbm) + " dBm" if any(x != "N/A" for x in tx_dbm) else "N/A",
                "diag_flags": "; ".join(flags) if flags else "OK"
            }
    except Exception:
        pass
    return dom_data

# ---------------------------------------------------------------- 主扫描逻辑
def scan_ifaces():
    results = []
    net_path = "/sys/class/net"
    niccli_dom = get_niccli_dom()

    for iface in os.listdir(net_path):
        driver_link = os.path.join(net_path, iface, "device/driver")
        if os.path.islink(driver_link):
            driver_name = os.path.basename(os.readlink(driver_link))
            if driver_name == "bnxt_en":
                info = {
                    "iface": iface,
                    "link": "Down",
                    "speed": "N/A",
                    "crc_errors": 0,
                    "fec_uncorr": 0,
                    "fec_corr": 0,
                    "temp": "N/A",
                    "vendor_pn": "N/A",
                    "vendor_sn": "N/A",
                    "rx_power": "N/A",
                    "tx_power": "N/A",
                    "diag_flags": "OK"
                }

                # 1. 链路与速率 (sysfs 优先，ethtool 兜底)
                oper = rd(f"/sys/class/net/{iface}/operstate")
                info["link"] = "Up" if oper == "up" else "Down"
                spd = rd(f"/sys/class/net/{iface}/speed")
                if spd and spd.lstrip("-").isdigit() and int(spd) > 0:
                    info["speed"] = f"{spd}Mb/s"

                # 2. CRC 与 FEC 统计 (ethtool -S)
                stats_out = run_cmd(f"ethtool -S {iface}")
                for line in stats_out.splitlines():
                    kv = line.strip().split(":")
                    if len(kv) == 2:
                        key = kv[0].strip().lower()
                        try:
                            val = int(kv[1].strip())
                            if key in ["rx_fcs_errors", "rx_crc_errors", "rx_frame_errors"]:
                                info["crc_errors"] += val
                            elif key in ["rx_fec_uncorrectable_blocks", "rx_fec_uncorr_blocks", "rx_fec_uncorrectable_words"]:
                                info["fec_uncorr"] += val
                            elif key in ["rx_fec_corrected_blocks", "rx_fec_corr_blocks"]:
                                info["fec_corr"] += val
                        except ValueError:
                            pass

                # 3. 仅当物理链路为 UP 时，才关联与填充光模块信息
                if info["link"] == "Up":
                    if iface in niccli_dom:
                        info.update(niccli_dom[iface])
                    else:
                        # ethtool 兜底文本提取
                        m_out = run_cmd(f"ethtool -m {iface}")
                        if m_out:
                            sn_m = re.search(r"Vendor\s+(?:SN|sn)\s*:\s*([^\n]+)", m_out)
                            pn_m = re.search(r"Vendor\s+(?:PN|pn)\s*:\s*([^\n]+)", m_out)
                            temp_m = re.search(r"(?:Module|Sensor)\s+temperature\s*:\s*([^\n]+)", m_out, re.I)
                            rx_powers = re.findall(r"(?:Receiver signal average optical power|Rx\d*\s+power)\s*:\s*([^\n]+)", m_out, re.I)
                            tx_powers = re.findall(r"(?:Laser output power|Tx\d*\s+power)\s*:\s*([^\n]+)", m_out, re.I)

                            if sn_m: info["vendor_sn"] = sn_m.group(1).strip()
                            if pn_m: info["vendor_pn"] = pn_m.group(1).strip()
                            if temp_m: info["temp"] = temp_m.group(1).strip()
                            if rx_powers: info["rx_power"] = "/".join([p.strip() for p in rx_powers[:4]])
                            if tx_powers: info["tx_power"] = "/".join([p.strip() for p in tx_powers[:4]])

                results.append(info)

    # 单行输出 JSON，方便 Ansible 直接正则捕获
    print(json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    scan_ifaces()
