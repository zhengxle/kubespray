#!/bin/bash

set -u

declare -A NAME_MAP=(
    ["bond_compute0"]="bond_c0"
    ["bond_compute1"]="bond_c1"
    ["bond_compute2"]="bond_c2"
    ["bond_compute3"]="bond_c3"
)

RDMA_CMD="/opt/mellanox/iproute2/sbin/rdma"

if [ ! -x "$RDMA_CMD" ]; then
    echo "Error: $RDMA_CMD not found or not executable." >&2
    exit 1
fi

for NETDEV in "${!NAME_MAP[@]}"; do
    NEW_NAME="${NAME_MAP[$NETDEV]}"

    CURRENT_DEV=""

    for i in {1..30}; do
        CURRENT_DEV=$(
            "$RDMA_CMD" link show 2>/dev/null |
            awk -v netdev="$NETDEV" '
                $0 ~ ("netdev " netdev "([[:space:]]|$)") {
                    split($2, a, "/")
                    print a[1]
                    exit
                }
            '
        )

        if [ -n "$CURRENT_DEV" ]; then
            break
        fi

        echo "Waiting for RDMA device of netdev $NETDEV... ($i/30)"
        sleep 1
    done

    if [ -z "$CURRENT_DEV" ]; then
        echo "Error: No RDMA device found for netdev $NETDEV after 30 seconds." >&2
        continue
    fi

    if [ "$CURRENT_DEV" = "$NEW_NAME" ]; then
        echo "RDMA dev for $NETDEV is already $NEW_NAME, skipping."
        continue
    fi

    echo "Renaming RDMA dev for $NETDEV: $CURRENT_DEV -> $NEW_NAME"

    if ! "$RDMA_CMD" dev set "$CURRENT_DEV" name "$NEW_NAME"; then
        echo "Error: Failed to rename RDMA device $CURRENT_DEV -> $NEW_NAME" >&2
        continue
    fi

    echo "Successfully renamed $CURRENT_DEV -> $NEW_NAME"
done
