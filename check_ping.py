import pandas as pd
import subprocess
import os
import re
from concurrent.futures import ThreadPoolExecutor

CSV_FILE = 'server_sn_ip.csv'

def get_node_name(hostname):
    """提取主机名最后的数字，转换为 nodex 格式（如 智算节点服务器-001 -> node1）"""
    match = re.search(r'-(\d+)$', str(hostname).strip())
    if match:
        node_num = int(match.group(1)) # 转为 int 自动去掉前导 zero
        return f"!node{node_num}"
    return str(hostname)

def ping_ip(ip):
    """检测单个 IP 是否能 ping 通"""
    if not ip or pd.isna(ip):
        return False
    # Linux/Mac 使用 -c 1 -W 1，Windows 使用 -n 1 -w 1000
    param = '-n 1 -w 1000' if os.name == 'nt' else '-c 1 -W 1'
    cmd = f"ping {param} {ip}"
    return subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def main():
    # 读取 CSV 文件
    df = pd.read_csv(CSV_FILE)
    
    unreachable_nodes = []
    tasks = []

    # 多线程并行校验，加快速度
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for index, row in df.iterrows():
            hostname = row['Hostname']
            ip = row['Business_IP']
            node_name = get_node_name(hostname)
            futures.append((node_name, executor.submit(ping_ip, ip)))
        
        for node_name, future in futures:
            if not future.result():
                unreachable_nodes.append(node_name)

    # 格式化输出为 node1,node2,nodex
    if unreachable_nodes:
        print(",".join(unreachable_nodes))
    else:
        print("所有节点 Business_IP 均通畅！")

if __name__ == '__main__':
    main()
