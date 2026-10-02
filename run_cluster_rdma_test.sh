#!/bin/bash
START_NODE=1
END_NODE=128
TOTAL_NODES=$(( END_NODE - START_NODE + 1 ))
INVENTORY="inventory/my-cluster/hosts.yml"
MAX_PARALLEL=1   # 并发数，可根据控制机资源和网络带宽调整

run_test() {
    local i=$1
    local c_num=$i
    local s_num=$(( START_NODE + ( (i - START_NODE + 1) % TOTAL_NODES ) ))

    local client_node="node${c_num}"
    local server_node="node${s_num}"

    echo "========================================================"
    echo "正在测试: ${client_node} (ID: ${c_num}) -> ${server_node} (ID: ${s_num})"
    echo "========================================================"

    ansible-playbook -i ${INVENTORY} run_rdma_test.yml \
      -e "target_client=${client_node}" \
      -e "target_server=${server_node}" \
      -e "duration=10"

    # 清理 Server 端残留进程
    ansible "${server_node}" -i ${INVENTORY} -m shell \
      -a "killall -9 ib_write_bw || true" --become > /dev/null 2>&1
}

export -f run_test
export INVENTORY

# 两轮测试，实现完整环路覆盖
for round in 1 2; do
    echo "################ 第 ${round} 轮测试开始 ################"

    for ((i=START_NODE; i<=END_NODE; i++)); do
        # 控制并发数量
        while (( $(jobs -rp | wc -l) >= MAX_PARALLEL )); do
            sleep 0.2
        done
        run_test "$i" &
    done

    # 等待本轮所有后台任务结束
    wait
    echo "################ 第 ${round} 轮测试完成 ################"
done

echo "node${START_NODE}~node${END_NODE} 节点轮询测试完成，正在生成测试报告..."
python3 /mnt/nfs_data/rdma_rail_test/generate_report.py
