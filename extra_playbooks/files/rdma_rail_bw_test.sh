#!/usr/bin/env bash
set -u
set -o pipefail

# Broadcom RoCE LAG / 4 Compute Rails + 1 Storage Rail bandwidth test
RAIL_COUNT=5
BASE_COMPUTE_NET="172.19"

MSG_SIZE=${MSG_SIZE:-4194304}
QP=${QP:-${QPS:-8}}
TX_DEPTH=${TX_DEPTH:-128}
DURATION=${DURATION:-30}
PORT_BASE=${PORT_BASE:-18515}
LOG_DIR=${LOG_DIR:-./rdma_rail_logs}
VERB=${VERB:-write}   # write | read | send
GID_INDEX=${GID_INDEX:-3} # RoCEv2 默认 GID 索引
USE_BIND_SOURCE=0

SERVER_PIDS=()

declare -A bond_map

bond_map['bond_c0']="2"
bond_map['bond_c1']="0"
bond_map['bond_c2']="6"
bond_map['bond_c3']="4"
bond_map['bond_s0']="-1"

usage() {
    cat <<'USAGE'
Usage:
  Server mode:
    sudo ./rdma_rail_bw_test.sh server <node_id>

  Client mode:
    sudo ./rdma_rail_bw_test.sh client <local_node_id> <remote_node_id>

Environment variables:
  QP=8 / QPS=8         Number of QPs per rail (Default: 8)
  GID_INDEX=3          RoCE v2 GID index (Default: 3)
  MSG_SIZE=4194304     Message size in bytes
  TX_DEPTH=128         TX queue depth
  DURATION=30          Test duration in seconds
  PORT_BASE=18515      TCP/CM port for rail0; railN uses PORT_BASE+N
  LOG_DIR=...          Output directory
  VERB=write           write | read | send
USAGE
}

log() {
    echo "[$(date '+%F %T')] $*"
}

err() {
    echo "ERROR: $*" >&2
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        err "command not found: $1"
        exit 1
    }
}

valid_node_id() {
    [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 254 ))
}

rail_netdev() {
    local rail="$1"
    if (( rail < 4 )); then
        echo "bond_compute${rail}"
    else
        echo "bond_storage0"
    fi
}

rail_rdmadev() {
    local rail="$1"
    if (( rail < 4 )); then
        echo "bond_c${rail}"
    else
        # 1. 优先检查是否存在明确的 bond_s0 或 bnxt_re_bond0
        if rdma dev 2>/dev/null | grep -qw "bond_s0"; then
            echo "bond_s0"
        elif rdma dev 2>/dev/null | grep -qw "bnxt_re_bond0"; then
            echo "bnxt_re_bond0"
        else
            # 2. 如果通过 rdma link 动态查找，使用 awk 精准提取第一列（斜杠前的设备名）
            local auto_dev
            auto_dev=$(rdma link 2>/dev/null | grep "netdev bond_storage0" | awk '{print $2}' | cut -d/ -f1 | head -n1 || true)
            if [[ -n "$auto_dev" ]]; then
                echo "$auto_dev"
            else
                echo "bond_s0"
            fi
        fi
    fi
}

rail_ip_local() {
    local rail="$1" node="$2"
    if (( rail < 4 )); then
        echo "${BASE_COMPUTE_NET}.${rail}.${node}"
    else
        local netdev
        netdev=$(rail_netdev "$rail")
        # local ip
        # ip=$(ip -4 -o addr show dev "$netdev" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1 || true)
        # if [[ -z "$ip" ]]; then
        #     err "Failed to detect local IPv4 address on ${netdev}"
        #     return 1
        # fi
        echo "$ip"
    fi
}

rail_ip_remote() {
    local rail="$1" local_node="$2" remote_node="$3"
    if (( rail < 4 )); then
        echo "${BASE_COMPUTE_NET}.${rail}.${remote_node}"
    else
        local local_storage_ip
        local_storage_ip=$(rail_ip_local "$rail" "$local_node")
        local prefix
        prefix=$(echo "$local_storage_ip" | cut -d. -f1-3)
        echo "${prefix}.${remote_node}"
    fi
}

rail_port() {
    echo $((PORT_BASE + $1))
}

pick_bw_tool() {
    local path="/opt/maca/samples/mccl_tests/ib_perf/tests"
    case "$VERB" in
        write) echo "$path/ib_write_bw" ;;
        read)  echo "$path/ib_read_bw" ;;
        send)  echo "$path/ib_send_bw" ;;
        *) err "VERB must be write, read, or send"; exit 1 ;;
    esac
}

preflight() {
    require_cmd ip
    require_cmd rdma
    local tool
    tool=$(pick_bw_tool)
    require_cmd "$tool"
}

check_rail_local() {
    local rail="$1" node="$2" ip="$3"
    local netdev rdmadev
    # ip=$(rail_ip_local "$rail" "$node") || return 1
    netdev=$(rail_netdev "$rail")
    rdmadev=$(rail_rdmadev "$rail")

    # if ! ip -o link show dev "$netdev" >/dev/null 2>&1; then
    #     err "Netdev ${netdev} does not exist"
    #     return 1
    # fi

    # if ! ip -4 -o addr show dev "$netdev" | grep -qw "$ip"; then
    #     err "${netdev} does not have IPv4 ${ip}"
    #     return 1
    # fi

    # if ! rdma dev 2>/dev/null | grep -qw "$rdmadev"; then
    #     err "RDMA device ${rdmadev} not found in 'rdma dev'"
    #     return 1
    # fi

    log "rail${rail} ($( [ $rail -eq 4 ] && echo "Storage" || echo "Compute" )): netdev=${netdev}, rdmadev=${rdmadev}, ip=${ip}, port=$(rail_port "$rail")"
}

server_one() {
    local rail="$1" node="$2" ip="$3"
    local dev port tool outfile
    # ip=$(rail_ip_local "$rail" "$node")
    dev=$(rail_rdmadev "$rail")
    port=$(rail_port "$rail")
    tool=$(pick_bw_tool)
    outfile="${LOG_DIR}/server_rail${rail}_${ip}.log"

    : > "$outfile"
    log "SERVER rail${rail}: ${dev} ${ip}:${port} -> ${tool} (QP=${QP}, GID=${GID_INDEX})"


    local perf_gpu=${bond_map["$dev"]}
    local cmd=(
        "$tool"
        -d "$dev"
        -x "$GID_INDEX"
        -p "$port"
        -s "$MSG_SIZE"
        -q "$QP"
        -t "$TX_DEPTH"
        -F 
        --report_gbits
        -D "$DURATION"
    )
    
    local perf_gpu=${bond_map["$dev"]}
    if [ "$perf_gpu" -ne "-1" ]; then
        cmd+=(--use_maca "$perf_gpu")
    fi

    "${cmd[@]}" >> "$outfile" 2>&1 &
    SERVER_PIDS+=($!)
}

run_client_one() {
    local rail="$1" local_node="$2" remote_node="$3" src_ip="$4" dst_ip="$5"
    local netdev rdmadev port tool outfile
    netdev=$(rail_netdev "$rail")
    rdmadev=$(rail_rdmadev "$rail")
    port=$(rail_port "$rail")
    tool=$(pick_bw_tool)
    outfile="${LOG_DIR}/client_rail${rail}_${src_ip}_to_${dst_ip}_q${QP}.log"

    log "CLIENT rail${rail}: ${src_ip} -> ${dst_ip}, netdev=${netdev}, rdmadev=${rdmadev}, port=${port}, QP=${QP}, size=${MSG_SIZE}"

    local cmd=(
        "$tool"
        -d "$rdmadev"
        -x "$GID_INDEX"
        -p "$port"
        -s "$MSG_SIZE"
        -q "$QP"
        -t "$TX_DEPTH"
        -D "$DURATION"
        -F 
        --report_gbits
    )
    local perf_gpu=${bond_map["$rdmadev"]}
    if [ "$perf_gpu" -ne "-1" ]; then
        cmd+=(--use_maca "$perf_gpu")
    fi

    cmd+=("$dst_ip")

    "${cmd[@]}" > "$outfile" 2>&1
    return $?
}

print_client_result() {
    local rail="$1" local_node="$2" remote_node="$3" src_ip="$4" dst_ip="$5"
    local outfile
    outfile="${LOG_DIR}/client_rail${rail}_${src_ip}_to_${dst_ip}_q${QP}.log"

    echo "========== rail${rail} ($( [ $rail -eq 4 ] && echo "Storage" || echo "Compute" )) result =========="
    if grep -q "BW average" "$outfile" 2>/dev/null; then
        grep -E 'BW average|BW peak|Gb/sec|Gbit|Mpps|MB/sec' "$outfile" | tail -5 || true
        echo "log: $outfile"
    else
        echo "FAILED"
        tail -15 "$outfile" 2>/dev/null || true
    fi
    echo "========================================="
    echo
}

cleanup_server() {
    local rc=$?
    if ((${#SERVER_PIDS[@]} > 0)); then
        log "Stopping server listeners..."
        kill "${SERVER_PIDS[@]}" 2>/dev/null || true
        wait "${SERVER_PIDS[@]}" 2>/dev/null || true
    fi
    exit "$rc"
}

server_mode() {
    local node="$1" ip="$2"
    valid_node_id "$node" || { err "node_id must be 1..254"; exit 2; }
    mkdir -p "$LOG_DIR"
    preflight

    trap cleanup_server INT TERM EXIT

    log "Starting 5 rail listeners (4 Compute + 1 Storage) on node ${node}"
    log "Config: msg=${MSG_SIZE}, qp=${QP}, gid_idx=${GID_INDEX}, tx_depth=${TX_DEPTH}, duration=${DURATION}, verb=${VERB}"

    local rail
    for ((rail=0; rail<RAIL_COUNT; rail++)); do
        # check_rail_local "$rail" "$node" || exit 1
        server_one "$rail" "$node" "$ip"
    done

    log "All 5 listeners started. Keep this terminal running while client tests execute."
    wait
}

client_mode() {
    local local_node="$1" remote_node="$2" client_ip="$3" server_ip="$4"
    valid_node_id "$local_node" || { err "local_node_id must be 1..254"; exit 2; }
    valid_node_id "$remote_node" || { err "remote_node_id must be 1..254"; exit 2; }
    mkdir -p "$LOG_DIR"
    preflight

    log "Starting Client parallel testing (4 Compute + 1 Storage): Node $local_node -> Node $remote_node (QP=${QP}, GID=${GID_INDEX})"

    local rail
    # for ((rail=0; rail<RAIL_COUNT; rail++)); do
    #     check_rail_local "$rail" "$local_node" || exit 1
    # done

    local client_pids=()
    for ((rail=0; rail<RAIL_COUNT; rail++)); do
        run_client_one "$rail" "$local_node" "$remote_node" "$client_ip" "$server_ip"  &
        client_pids+=($!)
        sleep 0.2
    done

    local failed=0
    for pid in "${client_pids[@]}"; do
        wait "$pid" || failed=$((failed + 1))
    done

    # 测试完成后顺序打印结果，避免控制台输出交错
    echo
    for ((rail=0; rail<RAIL_COUNT; rail++)); do
        print_client_result "$rail" "$local_node" "$remote_node" "$client_ip" "$server_ip"
    done

    if (( failed > 0 )); then
        err "$failed rails failed in client test."
        exit 1
    fi
    log "All 5 client rail tests completed successfully."
}

main() {
    if [[ $# -lt 1 ]]; then
        usage
        exit 1
    fi

    local mode="$1"
    shift

    case "$mode" in
        server)
            if [[ $# -ne 2 ]]; then usage; exit 1; fi
            server_mode "$1" "$2"
            ;;
        client)
            if [[ $# -ne 4 ]]; then usage; exit 1; fi
            client_mode "$1" "$2" "$3" "$4"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
