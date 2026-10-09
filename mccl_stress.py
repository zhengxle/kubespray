#!/usr/bin/env python3
import sys
import os
import argparse
import time
import datetime
import subprocess


# ------------------------------------------------------
#  convert_ips
# ------------------------------------------------------
def convert_ips(ip_num, file):
    if not os.path.exists(file):
        raise FileNotFoundError(f"convert_ips: file not found: {file}")

    groups = []
    group_result = []
    counter = 0

    with open(file, "r") as f:
        for line in f:
            ip = line.strip()
            if not ip:
                continue

            group_result.append(f"{ip}:8")
            counter += 1

            if counter == ip_num:
                groups.append(",".join(group_result))
                group_result = []
                counter = 0

    if group_result:
        groups.append(",".join(group_result))

    return groups


# ------------------------------------------------------
#  parse_duration("120m") 或 "2h"
# ------------------------------------------------------
def parse_duration(duration_str):
    d = duration_str.strip().lower()

    if d.endswith("m"):
        return int(float(d[:-1]) * 60)

    if d.endswith("h"):
        return int(float(d[:-1]) * 3600)

    raise ValueError("Invalid duration format. Use '10m' or '2h'")


# ------------------------------------------------------
#  run_test (single MCCL perf invocation)
# ------------------------------------------------------
def run_test(iter_idx, log_file, alg, card_num, host_ip,
             maca_path, ip_mask, ib_port, nic_name):

    begin_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, "a") as f:
        f.write("###############################\n")
        f.write(f"[iter {iter_idx}] - start time: {begin_time}\n")

    bench_name = f"{maca_path}/samples/mccl_tests/perf/mccl_perf/{alg}"

    perf_env = "-x FORCE_ACTIVE_WAIT=2 -x MCCL_IB_TC=160"
    lib_path_env = f"-x LD_LIBRARY_PATH={maca_path}/lib:{maca_path}/ompi/lib"

    env_var = (f"-x MCCL_IB_HCA={ib_port} -x MCCL_SOCKET_IFNAME={nic_name} "
               f"-x MCCL_CROSS_NIC=1 -x MCCL_FAST_WRITE_BACK=1 "
               f"-x MCCL_EARLY_WRITE_BACK=15 {perf_env} {lib_path_env}")

    testcmd = (
        f"{maca_path}/ompi/bin/mpirun -n {card_num} "
        f"-mca plm_rsh_num_concurrent 256 "
        f"-mca pml ^ucx -mca btl ^openib -mca routed direct "
        f"-mca osc ^ucx -mca btl_tcp_if_include {ip_mask} "
        f"-mca oob_tcp_if_include {ip_mask} {env_var} "
        f"-host {host_ip} {bench_name} -b 1K -e 2G -d float -f 2 -n 200"
    )

    with open(log_file, "a") as f:
        f.write(testcmd + "\n")

    # 执行 command
    with open(log_file, "a") as f:
        proc = subprocess.Popen(testcmd, shell=True, stdout=f, stderr=f)
        proc.wait()

    time.sleep(2)
    end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, "a") as f:
        f.write(f"[iter {iter_idx}] - end time: {end_time}\n\n")


# ------------------------------------------------------
#  mccl_cluster_stress
# ------------------------------------------------------
def mccl_cluster_stress(duration_sec, alg, card_num, host_ip):
    maca_path = "/opt/maca"
    ip_mask = "bond0"
    ib_port = "bond_c0,bond_c1,bond_c2,bond_c3"
    nic_name = "bond0"

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    log_file = f"report_mccl_stress_{alg}_{timestamp}.log"

    # 写头部
    with open(log_file, "a") as f:
        f.write(f"MCCL test alg: {alg}\n")
        f.write(f"MCCL test node: {host_ip}\n")
        f.write(f"MCCL test hca: {ib_port}\n")

    # 计算结束时间
    end_ts = int(time.time()) + duration_sec
    iter_idx = 1

    while int(time.time()) < end_ts:
        time.sleep(3)
        run_test(iter_idx, log_file, alg, card_num, host_ip,
                 maca_path, ip_mask, ib_port, nic_name)
        iter_idx += 1

    # 结束写入
    with open(log_file, "a") as f:
        f.write(f"MCCL test alg: {alg}\n")
        f.write(f"MCCL test node: {host_ip}\n")
        f.write(f"MCCL test hca: {ib_port}\n")


# ------------------------------------------------------
#  main controller
# ------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Python rewrite of MCCL stress Bash script")
    parser.add_argument("perf_type", help="例如 all_reduce_perf")
    parser.add_argument("node_num", type=int, help="每组节点数")
    parser.add_argument("ip_file", help="IP 文件")
    parser.add_argument("duration", help="持续时间，例如 120m 或 2h")
    args = parser.parse_args()

    perf_type = args.perf_type
    node = args.node_num
    file = args.ip_file
    duration_str = args.duration

    print(f"File: {file}")
    print(f"Duration: {duration_str}")

    duration_sec = parse_duration(duration_str)
    card_num = node * 8

    groups = convert_ips(node, file)
    group_idx = 1

    for line in groups:
        print(f"Group {group_idx} : {line}")

        # 后台启动 worker
        subprocess.Popen(
            [sys.executable, __file__, "worker",
             str(duration_sec), perf_type, str(card_num), line]
        )

        group_idx += 1
        time.sleep(2)

    print("All MCCL stress tasks launched.")


# ------------------------------------------------------
#  Worker mode
# ------------------------------------------------------
if __name__ == "__main__":
    # worker 模式：python mccl_stress.py worker <duration_sec> <alg> <card_num> <host_ip>
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        _, _, duration_sec, alg, card_num, host_ip = sys.argv
        mccl_cluster_stress(int(duration_sec), alg, int(card_num), host_ip)
    else:
        main()

