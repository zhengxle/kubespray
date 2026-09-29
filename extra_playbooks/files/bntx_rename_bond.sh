#!/bin/bash

set -u

# 定义计算网卡与存储网卡的映射关系: [netdev接口名]="期望的RDMA设备名"
declare -A NAME_MAP=(
    # 计算网卡
    ["bond_compute0"]="bond_c0"
    ["bond_compute1"]="bond_c1"
    ["bond_compute2"]="bond_c2"
    ["bond_compute3"]="bond_c3"
    
    # 存储网卡
    ["bond_storage0"]="bond_s0"
)

RDMA_CMD="/opt/mellanox/iproute2/sbin/rdma"

if [ ! -x "$RDMA_CMD" ]; then
    echo "Error: $RDMA_CMD not found or not executable." >&2
    exit 1
fi

for NETDEV in "${!NAME_MAP[@]}"; do
    NEW_NAME="${NAME_MAP[$NETDEV]}"

    # 动态匹配 netdev 对应的当前 RDMA 设备名
    CURRENT_DEV=$($RDMA_CMD link show | grep -E "netdev ${NETDEV}([[:space:]]|$)" | awk '{print $2}' | cut -d'/' -f1)

    if [ -z "$CURRENT_DEV" ]; then
        echo "Warning: No RDMA device found for netdev $NETDEV"
        continue
    fi

    if [ "$CURRENT_DEV" != "$NEW_NAME" ]; then
        echo "Renaming RDMA dev for $NETDEV: $CURRENT_DEV -> $NEW_NAME"
        $RDMA_CMD dev set "$CURRENT_DEV" name "$NEW_NAME"
    else
        echo "RDMA dev for $NETDEV is already $NEW_NAME, skipping."
    fi
done
