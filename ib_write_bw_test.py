import os
import re
import time
import logging
import shlex
import subprocess
from itertools import product, combinations
from typing import List, Tuple, Generator
import multiprocessing as mp
from multiprocessing import Manager
from logging.handlers import QueueHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from tqdm import tqdm
import argparse


def setup_logging(queue):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    queue_handler = QueueHandler(queue)
    logger.addHandler(queue_handler)


def log_listener_process(queue):
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler('perftest.log')
    stream_handler = logging.StreamHandler()
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    while True:
        try:
            record = queue.get()
            if record is None:
                break
            file_handler.handle(record)
            stream_handler.handle(record)
        except Exception:
            import traceback
            traceback.print_exc()


class PerfTestConfig:
    def __init__(self, mode: str, ip_file_path: str, bw: int):
        self.ssh_port = 22
        self.mode = mode
        self.bw = bw
        self.username = os.getenv('PERF_TEST_USER', 'root')
        self.password = os.getenv('PERF_TEST_PASS', 'calvin')
        self.node_list = []
        self.ip_file_path = ip_file_path
        try:
            with open(self.ip_file_path, 'r') as file:
                for line in file:
                    ip_address = line.strip()
                    if ip_address:
                        self.node_list.append(ip_address)
            logging.info(f"IP addresses loaded from '{self.ip_file_path}': {self.node_list}")
        except FileNotFoundError:
            print(f"Error: File '{self.ip_file_path}' not found. Using default node list.")
            self.node_list = [f"10.200.146.{idx}" for idx in range(14, 28)]
        self.network_interfaces = (
            'bond_c0', 'bond_c1', 'bond_c2', 'bond_c3'
        )
        self.min_port = 40000
        self.max_port = 60000


class PerfTestRunner:
    def __init__(self, config: PerfTestConfig, manager: Manager):
        self.config = config
        self.timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        self.result_dir = f"perftest_result_{self.timestamp}"
        self._create_directory()
        self.port_pool = manager.list(range(config.min_port, config.max_port + 1))
        self.port_lock = manager.Lock()

    def _create_directory(self):
        try:
            os.makedirs(self.result_dir, exist_ok=True)
            logging.info(f"Created result directory: {self.result_dir}")
        except OSError as e:
            logging.error(f"Directory creation failed: {e}")
            raise

    def create_remote_directories(self):
        cmd = "mkdir -p ./rping; rm -f -R ./rping/*"
        logging.info("在远程节点上创建rping目录")
        def create_host(host):
            self._ssh_execute(host, cmd)
        with ThreadPoolExecutor(max_workers=20) as executor:
            executor.map(create_host, self.config.node_list)
        time.sleep(5)

    def collect_results(self):
        local_dir = os.path.join(self.result_dir, 'rping_results')
        os.makedirs(local_dir, exist_ok=True)
        logging.info("开始收集log文件")
        def transfer_host(host):
            remote_path = f"{host}:./rping/*"
            local_path = os.path.join(local_dir, host)
            os.makedirs(local_path, exist_ok=True)
            scp_cmd = (
                f"scp -P {self.config.ssh_port} "
                f"-o StrictHostKeyChecking=no -r {remote_path} {local_path}/"
            )
            try:
                subprocess.run(
                    scp_cmd,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
            except subprocess.CalledProcessError as e:
                logging.error(f"從節點 {host} 收集文件失敗: {e.stderr}")
            except subprocess.TimeoutExpired:
                logging.error(f"從節點 {host} 收集文件超時")
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(transfer_host, self.config.node_list)
        time.sleep(5)
        logging.info("log文件收集结束")
        self.process_log_files(local_dir)

    def extract_bw_average_from_text(self,content):
        """从文本中提取 BW average 值"""
        lines = content.splitlines()

        # 找到包含 BW average 的标题行
        header_line = None
        for line in lines:
            if 'BW average' in line:
                header_line = line.strip()
                break

        if not header_line:
            return None  # 没有找到 BW average

        # 提取字段名
        headers = re.split(r'\s{2,}', header_line)
        try:
            bw_avg_index = headers.index('BW average[Gb/sec]')
        except ValueError:
            return None

        # 找到第一行数据
        for line in lines:
            if re.match(r'\s*\d', line):
                fields = re.split(r'\s{2,}', line.strip())
                if len(fields) > bw_avg_index:
                    return fields[bw_avg_index]
                else:
                    return None
        return None

    def process_log_files(self, log_dir):
        """处理所有日志文件并生成分析结果"""
        results = []
        results_faild = []
        ip_pattern = re.compile(r'^(\d+\.\d+\.\d+\.\d+)_(.+)$')

        for root, _, files in os.walk(log_dir):
            for filename in files:
                if not filename.endswith('.txt'):
                    continue
                try:
                    base_name = os.path.splitext(filename)[0]
                    part1, part2 = base_name.split('__')
                    ip1_match = ip_pattern.match(part1)
                    ip2_match = ip_pattern.match(part2)
                    if not ip1_match or not ip2_match:
                        logging.warning(f"文件名格式错误: {filename}")
                        continue
                    src_ip, src_interface = ip1_match.groups()
                    dst_ip, dst_interface = ip2_match.groups()
                except ValueError:
                    logging.warning(f"无效的文件名格式: {filename}")
                    continue

                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        bw_avg = self.extract_bw_average_from_text(content)
                        if bw_avg is None or float(bw_avg) < self.config.bw*0.975 :
                            results_faild.append({
                                'source_ip': src_ip,
                                'source_interface': src_interface,
                                'destination_ip': dst_ip,
                                'destination_interface': dst_interface,
                                'bandwidth_avg_gbps': bw_avg
                            })
                            continue
                        #mbps = bandwidth_match.group(1)
                except Exception as e:
                    logging.error(f"读取文件失败 {filename}: {str(e)}")
                    continue

                results.append({
                    'source_ip': src_ip,
                    'source_interface': src_interface,
                    'destination_ip': dst_ip,
                    'destination_interface': dst_interface,
                    'bandwidth_avg_gbps': bw_avg
                })

        if results:
            csv_path = os.path.join(self.result_dir, 'rdma_analysis_passed.csv')
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'source_ip',
                    'source_interface',
                    'destination_ip',
                    'destination_interface',
                    'bandwidth_avg_gbps'
                ])
                writer.writeheader()
                writer.writerows(results)
            logging.info(f"带宽分析结果已保存到 {csv_path}")
        else:
            logging.warning("没有找到有效数据")

        csv_path = os.path.join(self.result_dir, 'rdma_analysis_failed.csv')
        if results_faild:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'source_ip',
                    'source_interface',
                    'destination_ip',
                    'destination_interface',
                    'bandwidth_avg_gbps'
                ])
                writer.writeheader()
                writer.writerows(results_faild)
            logging.info(f"失败结果已保存到 {csv_path}")
        else:
            os.remove(csv_path)

    def generate_ip_combinations(self) -> Generator[Tuple[str, str], None, None]:
        if self.config.mode == "full_mesh":
            return (pair for pair in product(self.config.node_list, self.config.node_list)
                    if pair[0] != pair[1])
        else:
            return [tuple(sorted(pair)) for pair in combinations(self.config.node_list, 2)]

    def batch_generator(self, data: List[Tuple[str, str]]) -> Generator[List[Tuple[str, str]], None, None]:
        while data:
            used_ips = set()
            batch = []
            remaining = []
            for pair in data:
                ip1, ip2 = pair
                if ip1 not in used_ips and ip2 not in used_ips:
                    batch.append(pair)
                    used_ips.update({ip1, ip2})
                else:
                    remaining.append(pair)
            data = remaining
            yield batch

    def batch_generator_retry(self, data: List[Tuple[str, str, str, str]]) -> Generator[List[Tuple[str, str, str, str]], None, None]:
        while data:
            used_ips = set()
            batch = []
            remaining = []
            for pair in data:
                ip1, ip2, inter_1, inter_2= pair
                if ip1 not in used_ips and ip2 not in used_ips:
                    batch.append(pair)
                    used_ips.update({ip1, ip2})
                else:
                    remaining.append(pair)
            data = remaining
            yield batch

    def _ssh_execute(self, host: str, command: str) -> str:
        sanitized_cmd = shlex.quote(command)
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no {host} {sanitized_cmd}"
        try:
            result = subprocess.run(
                ssh_cmd,
                shell=True,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""

    def _execute_test_new(self, client_ip: str, server_ip: str, intf: str) -> dict:
        port = None
        try:
            with self.port_lock:
                if not self.port_pool:
                    raise ValueError("无可用端口")
                port = self.port_pool.pop()
            result_file = f"{self.result_dir}/{client_ip}_{intf}__{server_ip}_{intf}.txt"
            client_result_file = f"./rping/{client_ip}_{intf}__{server_ip}_{intf}.txt"
            # 修改服务器端命令，添加flock
            server_cmd = (
                f"nohup flock /tmp/ib_write_bw_{intf}.lock -c "
                f"'ib_write_bw -d {intf} -F -p {port} -s 65535 -x 3 --report_gbits' "
                f"> /dev/null 2>&1 &"
            )
            self._ssh_execute(server_ip, server_cmd)
            # 修改客户端命令，添加flock
            client_cmd = (
                f"flock /tmp/ib_write_bw_{intf}.lock -c "
                f"'ib_write_bw -d {intf} -F -p {port} -s 65535 -x 3 --report_gbits {server_ip}' "
                f"> {client_result_file} 2>&1 "
            )
            self._ssh_execute(client_ip, client_cmd)
        except Exception as e:
            logging.error(f"测试失败 {client_ip}->{server_ip}: {str(e)}")
            return {}
        finally:
            if port is not None:
                with self.port_lock:
                    if port not in self.port_pool:
                        self.port_pool.append(port)

    def _execute_test(self, client_ip: str, server_ip: str, intf: str) -> dict:
        port = None
        #time.sleep(sl)
        intf_to_maca = {
          "bond_c0": 2,
          "bond_c1": 0,
          "bond_c2": 6,
          "bond_c3": 4
        }
        use_maca = intf_to_maca.get(intf, 0)  # 默认 use_maca=0，如果接口未知
        try:
            with self.port_lock:
                if not self.port_pool:
                    raise ValueError("无可用端口")
                port = self.port_pool.pop()
            result_file = f"{self.result_dir}/{client_ip}_{intf}__{server_ip}_{intf}.txt"
            client_result_file = f"./rping/{client_ip}_{intf}__{server_ip}_{intf}.txt"
            server_cmd = f"nohup /opt/maca/samples/mccl_tests/ib_perf/tests/ib_write_bw --use_maca {use_maca} -d {intf} -F -q 2 -p {port} -s 65535 -x 3 --report_gbits > /dev/null 2>&1 &"
            self._ssh_execute(server_ip, server_cmd)
            #client_cmd = f"/opt/maca/samples/mccl_tests/ib_perf/tests/ib_write_bw --use_maca {use_maca} -d {intf} -F -q 2 -p {port} -s 65535 -x 3 --report_gbits {server_ip}  > {client_result_file} 2>&1 "
            client_cmd = (
                f'echo "[CMD] /opt/maca/samples/mccl_tests/ib_perf/tests/ib_write_bw '
                f'--use_maca {use_maca} -d {intf} -F -q 2 -p {port} -s 65535 -x 3 '
                f'--report_gbits {server_ip}" >> {client_result_file} 2>&1; '
                f'/opt/maca/samples/mccl_tests/ib_perf/tests/ib_write_bw '
                f'--use_maca {use_maca} -d {intf} -F -q 2 -p {port} -s 65535 -x 3 '
                f'--report_gbits {server_ip} >> {client_result_file} 2>&1'
            )
            self._ssh_execute(client_ip, client_cmd)
        except Exception as e:
            logging.error(f"测试失败 {client_ip}->{server_ip}: {str(e)}")
            return {}
        finally:
            if port is not None:
                with self.port_lock:
                    if port not in self.port_pool:
                        self.port_pool.append(port)

    def _execute_test_backup(self, client_ip: str, server_ip: str, intf: str, sl: int) -> dict:
        port = None
        time.sleep(sl)
        try:
            with self.port_lock:
                if not self.port_pool:
                    raise ValueError("无可用端口")
                port = self.port_pool.pop()
            result_file = f"{self.result_dir}/{client_ip}_{intf}__{server_ip}_{intf}.txt"
            client_result_file = f"./rping/{client_ip}_{intf}__{server_ip}_{intf}.txt"
            server_cmd = f"nohup ib_write_bw -d {intf} -F -p {port} -s 65535 -x 3 --report_gbits > /dev/null 2>&1 &"
            self._ssh_execute(server_ip, server_cmd)
            client_cmd = f"ib_write_bw -d {intf} -F -p {port} -s 65535 -x 3 --report_gbits {server_ip}  > {client_result_file} 2>&1 "
            self._ssh_execute(client_ip, client_cmd)
        except Exception as e:
            logging.error(f"测试失败 {client_ip}->{server_ip}: {str(e)}")
            return {}
        finally:
            if port is not None:
                with self.port_lock:
                    if port not in self.port_pool:
                        self.port_pool.append(port)

    def _parse_output(self, output: str) -> float:
        match = re.search(r"(\d+)\s+bytes in\s+(\d+\.\d+)\s+seconds =\s+([0-9.]+)\s+Mbit/sec", output)
        return float(match.group(3)) if match else 0.0

    def parallel_execute(self, batch: List[Tuple[str, str]]):
        max_workers = min(os.cpu_count() * 2, 128)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for client_ip, server_ip in batch:
                sleep_time = 0
                for intf in self.config.network_interfaces:
                    future = executor.submit(self._execute_test, client_ip, server_ip, intf)
                    sleep_time += 2
                    #time.sleep(1)
                    futures[future] = time.time()
            for future in as_completed(futures):
                submit_time = futures[future]
                timeout_remaining = 120 - (time.time() - submit_time)
                if timeout_remaining <= 0:
                    logging.warning("任务超时")
                    continue
                try:
                    future.result(timeout=timeout_remaining)
                except TimeoutError:
                    logging.warning("任务在允许时间内未完成")
                except Exception as e:
                    logging.error(f"任务执行失败: {e}")

    def parallel_execute_retry(self, batch: List[Tuple[str, str, str, str]]):
        max_workers = min(os.cpu_count() * 2, 128)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for client_ip, server_ip , client_inter, server_inter in batch:
                sleep_time = 0
                future = executor.submit(self._execute_test, client_ip, server_ip, client_inter)
                sleep_time += 2
                #time.sleep(1)
                futures[future] = time.time()
            for future in as_completed(futures):
                submit_time = futures[future]
                timeout_remaining = 120 - (time.time() - submit_time)
                if timeout_remaining <= 0:
                    logging.warning("任务超时")
                    continue
                try:
                    future.result(timeout=timeout_remaining)
                except TimeoutError:
                    logging.warning("任务在允许时间内未完成")
                except Exception as e:
                    logging.error(f"任务执行失败: {e}")

    def cleanup(self):
        logging.info("清理测试进程...")
        kill_cmd = "nohup pkill -f ib_write_bw > /dev/null 2>&1 &"
        def kill_host(host):
            self._ssh_execute(host, kill_cmd)
        with ThreadPoolExecutor(max_workers=20) as executor:
            executor.map(kill_host, self.config.node_list)
        time.sleep(5)


class FailFileParser:
    def __init__(self, filename):
        self.filename = filename
        self.links = []
        self._parse_file()

    def _parse_file(self):
        seen = set()
        with open(self.filename, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                source_ip = row['source_ip']
                destination_ip = row['destination_ip']
                source_device = row['source_interface']
                destination_device = row['destination_interface']
                pair = (source_ip, destination_ip,source_device,destination_device)
                if pair not in seen:
                    seen.add(pair)
                    self.links.append(pair)

    def get_links(self):
        return self.links


def retry_failed_tests(runner: PerfTestRunner, description: str):
    failed_csv_path = os.path.join(runner.result_dir, 'rdma_analysis_failed.csv')
    if os.path.exists(failed_csv_path) and os.path.getsize(failed_csv_path) > 0:
        parser = FailFileParser(failed_csv_path)
        failed_pairs = parser.get_links()
        if failed_pairs:
            logging.info(f"发现 {len(failed_pairs)} 对失败的测试，开始{description}重试...")
            runner.cleanup()
            #runner.create_remote_directories()
            with tqdm(
                total=len(failed_pairs),
                desc=f"{description}重试进度",
                unit="pair",
                dynamic_ncols=True,
                mininterval=0.3,
                maxinterval=1.0,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            ) as pbar_retry:
                for batch_num, batch in enumerate(runner.batch_generator_retry(failed_pairs), 1):
                    start_time = time.time()
                    runner.parallel_execute_retry(batch)
                    elapsed_time = time.time() - start_time
                    pbar_retry.update(len(batch))
                    pbar_retry.set_postfix_str(f"批次 #{batch_num} 耗时 {elapsed_time:.1f}s")
            time.sleep(10)
            runner.collect_results()


def main():
    parser = argparse.ArgumentParser(description='RDMA性能测试工具')
    parser.add_argument('--mode', type=str, default='half_full',
                        choices=['half_full', 'full_mesh'],
                        help='测试模式：half_full（默认）或 full_mesh')
    parser.add_argument('--ip_file_path', type=str, default='ips_list.txt',
                        help='包含IP地址列表的文件路径（默认为ips_list.txt）')
    parser.add_argument('--bw', type=int, default=200,
                        help='指定网口带宽，单位GB。请输入一个整数（默认值为200）')
    args = parser.parse_args()

    log_queue = mp.Queue()
    listener = mp.Process(target=log_listener_process, args=(log_queue,))
    listener.start()
    setup_logging(log_queue)
    try:
        with Manager() as manager:
            config = PerfTestConfig(mode=args.mode, ip_file_path=args.ip_file_path, bw=args.bw)
            runner = PerfTestRunner(config, manager)
            runner.cleanup()
            runner.create_remote_directories()
            test_pairs = list(runner.generate_ip_combinations())
            total_pairs = len(test_pairs)
            logging.info(f"总测试对数: {total_pairs}")

            with tqdm(
                total=total_pairs,
                desc="测试进度",
                unit="pair",
                dynamic_ncols=True,
                mininterval=0.3,
                maxinterval=1.0,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            ) as pbar:
                MAX_BATCH = 1000
                for batch_num, batch in enumerate(runner.batch_generator(test_pairs), 1):
                    if batch_num > MAX_BATCH:
                        logging.info(f"已完成 {MAX_BATCH} 个batch，提前结束测试")
                        break
                    start_time = time.time()
                    runner.parallel_execute(batch)
                    elapsed_time = time.time() - start_time
                    pbar.update(len(batch))
                    pbar.set_postfix_str(f"批次 #{batch_num} 耗时 {elapsed_time:.1f}s")
                logging.info("所有测试完成")
            time.sleep(10)
            runner.collect_results()
            # 两次重试失败的测试
            retry_failed_tests(runner, "第1次")
            retry_failed_tests(runner, "第2次")

    except Exception as e:
        logging.critical(f"严重错误: {str(e)}")
    finally:
        if 'runner' in locals():
            time.sleep(5)
            runner.cleanup()
        log_queue.put(None)
        listener.join()


if __name__ == "__main__":
    main()

