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

# 检查所有 netdev 是否都已出现在 rdma link show 中
check_all_netdev_ready() {
    local missing=()
    local netdev

    for netdev in "${!NAME_MAP[@]}"; do
        if ! $RDMA_CMD link show | grep -Eq "netdev ${netdev}([[:space:]]|$)"; then
            missing+=("$netdev")
        fi
    done

    if [ ${#missing[@]} -eq 0 ]; then
        return 0
    fi

    echo "Not ready netdevs: ${missing[*]}" >&2
    return 1
}

MAX_TRY=3
READY=0

for ((try=1; try<=MAX_TRY; try++)); do
    echo "=== netplan apply attempt ${try}/${MAX_TRY} ==="
    netplan apply

    # 等待 bond 聚合和 RDMA link 出现
    sleep 5

    if check_all_netdev_ready; then
        READY=1
        echo "All netdevs are ready."
        break
    fi
done

if [ "$READY" -ne 1 ]; then
    echo "Error: Not all netdevs became ready after ${MAX_TRY} attempts. Exiting." >&2
    exit 1
fi

# 所有 netdev 都就绪后再做重命名
for NETDEV in "${!NAME_MAP[@]}"; do
    NEW_NAME="${NAME_MAP[$NETDEV]}"

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
