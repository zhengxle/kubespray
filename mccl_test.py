import os
import subprocess
import statistics
import sys
import concurrent.futures
from datetime import datetime

# used for MACA version >=2.33
DEFAULT_TEST_BINS = [
    "all_gather_perf",
    "all_reduce_perf",
    "alltoall_perf",
    "broadcast_perf",
    "gather_perf",
    "reduce_perf",
    "reduce_scatter_perf",
    "scatter_perf",
    "sendrecv_perf",
]

def read_ips(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def parse_output(output):
    for line in output.split('\n'):
        if not line.startswith('#'):
            if "2147483648" in line and "nThread" not in line:
                parts = line.strip().split()
                if len(parts) >= 8:
                    try:
                        if "sum" in line:
                            return float(parts[7])
                        else:
                            return float(parts[6])
                    except (IndexError, ValueError):
                        continue
    return None

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def write_log(log_dir, group, result, value, cmd):
    ensure_dir(log_dir)
    logfile = os.path.join(log_dir, "run.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(logfile, "a") as f:
        f.write(f"\n[{timestamp}] {'+'.join(group)}\n")
        f.write(f"{cmd}\n")
        f.write("命令输出:\n")
        f.write(result.stdout)
        if result.stderr:
            f.write("\n错误信息:\n")
            f.write(result.stderr)
        f.write(f"\n返回值: {result.returncode} | 解析值: {value}\n")
        f.write("-" * 60 + "\n")

def run_test(group, test_bin, log_dir):
    try:
        host_arg = ",".join([f"{ip}:8" for ip in group])
        num_procs = len(group) * 8

        cmd = [
            '/opt/maca/ompi/bin/mpirun',
            '-np', str(num_procs),
            '--allow-run-as-root',
            '-host', host_arg,
            '-mca', 'btl_tcp_if_include', 'bond0',
            '-mca', 'oob_tcp_if_include', 'bond0',
            '-mca', 'pml', '^ucx',
            '-mca', 'osc', '^ucx',
            '-mca', 'btl', '^openib',
            '-mca', 'routed', 'direct',
            '-x', 'MCCL_IB_HCA=bond_c0,bond_c1,bond_c2,bond_c3',
            '-x', 'MCCL_SOCKET_IFNAME=bond0',
            '-x', 'LD_LIBRARY_PATH=/opt/maca/lib:/opt/maca/ompi/lib',
            '-x', 'MCCL_IB_TC=160',
            '-x', 'MCCL_FAST_WRITE_BACK=1',
            '-x', 'MCCL_EARLY_WRITE_BACK=15',
            '-x', 'MCCL_CROSS_NIC=1',
            '-x', 'MCCL_P2P_LEVEL=SYS',
            '-x', 'FORCE_ACTIVE_WAIT=1',
            f'/opt/maca/samples/mccl_tests/perf/mccl_perf/{test_bin}',
            '-b', '1K', '-e', '2G', '-d', 'float', '-f', '2', '-g', '1', '-n', '20'
            #'bash', '-c',
            #f'ulimit -n 1000000 && /opt/maca/samples/mccl_tests/perf/mccl_perf/{test_bin} -b 1K -e 8G -d float -f 2 -g 1 -n 10'
        ]
        #print(' '.join(cmd))
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=1000
        )

        value = parse_output(result.stdout)
        write_log(log_dir, group, result, value, cmd)
        return group, value

    except subprocess.TimeoutExpired:
        print(f"{'+'.join(group)} 执行超时")
        return group, None
    except Exception as e:
        print(f"{'+'.join(group)} 执行异常: {e}")
        return group, None

def main(ip_file, threshold, test_bins, parallel=True):
    ips = read_ips(ip_file)
    total_ips = len(ips)

    group_sizes = []
    size = 1
    while size <= total_ips:
        group_sizes.append(size)
        size *= 2

    print(f"IP 总数: {total_ips}")
    print(f"测试 group_size: {group_sizes}")
    print(f"测试工具: {test_bins}")
    print("-" * 60)

    for test_bin in test_bins:
        print(f"\n========== 测试工具: {test_bin} ==========")

        for group_size in group_sizes:
            print(f"\n--- group_size = {group_size} ---")

            if not parallel and group_size > 0:
                groups = [ips[:group_size]] if total_ips >= group_size else []
            else:
                groups = [
                    ips[i:i + group_size]
                    for i in range(0, total_ips, group_size)
                    if len(ips[i:i + group_size]) == group_size
                ]

            log_dir = os.path.join("logs", test_bin, f"group_{group_size}")

            results = []

            if parallel:
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(groups)) as executor:
                    futures = {
                        executor.submit(run_test, group, test_bin, log_dir): group
                        for group in groups
                    }
                    for future in concurrent.futures.as_completed(futures):
                        group, value = future.result()
                        results.append((group, value))
                        status = "✅" if value is not None and value >= threshold else "❌"
                        print(f"{status} {'+'.join(group):<40} : {value}")
            else:
                for group in groups:
                    group, value = run_test(group, test_bin, log_dir)
                    results.append((group, value))
                    status = "✅" if value is not None and value >= threshold else "❌"
                    print(f"{status} {'+'.join(group):<40} : {value}")

            success = [(g, v) for g, v in results if v is not None and v >= threshold]

            #print(f"\n结果统计 (group_size={group_size}):")
            #print(f"成功: {len(success)} / {len(results)}")

            #if success:
            #    values = [v for _, v in success]
            #    print(f"平均值: {statistics.mean(values):.2f}")
            #    print(f"最小值: {min(values):.2f}")
            #    print(f"最大值: {max(values):.2f}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法:")
        print("  python script.py <ip_file> <threshold> [test_bin] [--serial]")
        sys.exit(1)

    ip_file = sys.argv[1]
    threshold = float(sys.argv[2])

    parallel = True
    args = sys.argv[3:]
    if "--serial" in args:
        parallel = False
        args.remove("--serial")

    test_bins = args if args else DEFAULT_TEST_BINS

    main(ip_file, threshold, test_bins, parallel)


