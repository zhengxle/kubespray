#!/bin/bash
START_NODE=1
END_NODE=128
INVENTORY="inventory/my-cluster/hosts.yml"
MAX_PARALLEL=4

run_test() {
    local c_num=$1
    local s_num=$2
    
    # 防止自己打自己
    if [ "$c_num" -eq "$s_num" ]; then
        return
    fi

    local client_node="node${c_num}"
    local server_node="node${s_num}"

    echo "======================================================================"
    echo "正在测试： ${client_node} -> ${server_node}"
    echo "======================================================================"

    ansible-playbook -i ${INVENTORY} run_rdma_test.yml \
      -e "target_client=${client_node}" \
      -e "target_server=${server_node}" \
      -e "duration=10"

    # 清理 Server 端残留进程（只清理本组指定的 server）
    ansible "${server_node}" -i ${INVENTORY} -m shell \
      -a "killall -9 ib_write_bw || true" --become > /dev/null 2>&1
}

export -f run_test
export INVENTORY

# 两轮测试，实现完整交叉验证
for round in 1 2; do
    echo "############## 第 ${round} 轮测试开始 ##############"
    
    # 步长为2进行遍历，每次取出两个不重叠的节点
    for ((i=START_NODE; i<END_NODE; i+=2)); do
        
        if [ "$round" -eq 1 ]; then
            # 第一轮：奇数节点做 Client，偶数节点做 Server (1->2, 3->4, 5->6...)
            c=$i
            s=$((i+1))
        else
            # 第二轮：偶数节点做 Client，奇数节点做 Server (2->1, 4->3, 6->5...)
            c=$((i+1))
            s=$i
        fi

        # 控制并发数量
        while (( $(jobs -rp | wc -l) >= MAX_PARALLEL )); do
            sleep 0.2
        done
        
        # 放入后台执行，此时同一次循环内 c 和 s 绝对不会相同，也不会重叠
        run_test "$c" "$s" &
    done

    # 等待本轮所有后台任务结束
    wait
    echo "############## 第 ${round} 轮测试完成 ##############"
done

echo "节点交叉测试完成，正在生成测试报告..."
python3 /mnt/nfs_data/rdma_rail_test/generate_report.py
