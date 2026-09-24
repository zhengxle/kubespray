#!/bin/bash


#!/bin/bash
START_NODE=101
END_NODE=128
TOTAL_NODES=$(( END_NODE - START_NODE + 1 ))
INVENTORY="inventory/my-cluster/hosts.yml"

for ((i=START_NODE; i<=END_NODE; i++)); do
    c_num=$i

    # 计算下一个 Server 节点的 ID（保证在 33~49 之间形成环路）
    s_num=$(( START_NODE + ( (i - START_NODE + 1) % TOTAL_NODES ) ))

    client_node="node${c_num}"
    server_node="node${s_num}"

    echo "========================================================"
    echo "正在测试: ${client_node} (ID: ${c_num}) -> ${server_node} (ID: ${s_num})"
    echo "========================================================"

    ansible-playbook -i ${INVENTORY} run_rdma_test.yml \
      -e "target_client=${client_node}" \
      -e "target_server=${server_node}" \
      -e "duration=10"

    # 清理 Server 端残留进程
    ansible "${server_node}" -i ${INVENTORY} -m shell -a "killall -9 ib_write_bw || true" --become > /dev/null 2>&1
done

echo "node33~node49 节点轮询测试完成，正在生成测试报告..."
python3 /mnt/nfs_data/rdma_rail_test/generate_report.py

