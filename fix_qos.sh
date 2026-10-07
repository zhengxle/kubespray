#!/bin/bash
# 在所有节点所有物理口上统一 QoS 映射：DSCP 0 和 40 → Priority 5

for node in node1 node2 node3 node4 node5 node6 node7 node8; do
    echo "=== Configuring QoS on $node ==="
    ssh $node "sudo bash -c '
        # 遍历所有 bond 逻辑口
        for bond_dev in bond_compute0 bond_compute1 bond_compute2 bond_compute3 bond_storage0; do
            if [ -d /sys/class/net/\$bond_dev/bonding ]; then
                # 找到该 bond 下的所有物理口
                for slave in \$(cat /sys/class/net/\$bond_dev/bonding/slaves); do
                    echo \"  Configuring \$slave on \$bond_dev...\"
                    # 设置 DSCP 0 和 40 映射到 Priority 5
                    sudo mlnx_qos -i \$slave --dscp2prio set,0,5
                    sudo mlnx_qos -i \$slave --dscp2prio set,40,5
                done
            fi
        done
    '"
done
