#!/usr/bin/env bash
set -u
set -o pipefail

# Broadcom RoCE LAG / 4 Compute Rails + 1 Storage Rail bandwidth test
RAIL_COUNT=5
BASE_COMPUTE_NET="172.19"

MSG_SIZE=${MSG_SIZE:-4194304}
QP=${QPS:-1}
TX_DEPTH=${TX_DEPTH:-128}
DURATION=${DURATION:-30}
PORT_BASE=${PORT_BASE:-18515}
LOG_DIR=${LOG_DIR:-./rdma_rail_logs}
VERB=${VERB:-write}   # write | read | send
USE_BIND_SOURCE=0
SERVER_READY_SLEEP=${SERVER_READY_SLEEP:-2}

SERVER_PIDS=()

usage() {
    cat <<'USAGE'
Usage:
  Server mode:
    sudo ./rdma_rail_bw_test.sh server <node_id>

  Client mode:
    sudo ./rdma_rail_bw_test.sh client <local_node_id> <remote_node_id>

Environment variables:
  QPS=1                 Number of QPs. Example: QPS=32
  MSG_SIZE=4194304      Message size in bytes
  TX_DEPTH=128         TX queue depth
  DURATION=30          Test duration in seconds
  PORT_BASE=18515      TCP/CM port for rail0; railN uses PORT_BASE+N
  LOG_DIR=...         Output directory
  VERB=write          write | read | send
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

# 系统网络接口名称
rail_netdev() {
    local rail="$1"
    if (( rail < 4 )); then
        echo "bond_compute${rail}"
    else
        echo "bond_storage0"
    fi
}

# RDMA 设备名称
rail_rdmadev() {
    local rail="$1"
    if (( rail < 4 )); then
        echo "bond_c${rail}"
    else
        # 优先使用博通驱动默认生成的 bnxt_re_bond0，若没有则尝试由系统动态获取 netdev 对应的 rdma 设备
        if rdma dev 2>/dev/null | grep -qw "bnxt_re_bond0"; then
            echo "bnxt_re_bond0"
        else
            # 自动根据 netdev=bond_storage0 查找对应的 rdma 设备名
            local auto_dev
            auto_dev=$(rdma link 2>/dev/null | grep "netdev bond_storage0" | awk '{print $2}' | cut -d/ -f1 | head -n1 || true)
            if [[ -n "$auto_dev" ]]; then
                echo "$auto_dev"
            else
                echo "bond_storage0"
            fi
        fi
    fi
}

# 获取本地指定 Rail 的 IP (计算网按规则，存储网直接从网卡配置动态获取)
rail_ip_local() {
    local rail="$1" node="$2"
    if (( rail < 4 )); then
        echo "${BASE_COMPUTE_NET}.${rail}.${node}"
    else
        local netdev
        netdev=$(rail_netdev "$rail")
        # 从本地 bond_storage0 网卡实时读取第一个 IPv4 地址
        local ip
        ip=$(ip -4 -o addr show dev "$netdev" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1 || true)
        if [[ -z "$ip" ]]; then
            err "Failed to detect local IPv4 address on ${netdev}"
            return 1
        fi
        echo "$ip"
    fi
}

# 获取对端 Server 的 IP (计算网按规则，存储网通过路由/对端机器查询)
rail_ip_remote() {
    local rail="$1" local_node="$2" remote_node="$3"
    if (( rail < 4 )); then
        echo "${BASE_COMPUTE_NET}.${rail}.${remote_node}"
    else
        # 存储网对端 IP 获取：优先尝试通过 ansible/ssh 或 DNS，若本地 172.18 网段，将末位替换为 remote_node
        local local_storage_ip
        local_storage_ip=$(rail_ip_local "$rail" "$local_node")
        
        # 提取本地存储网 IP 的前三段 (172.18.xx)，拼接对端 node_id (yy)
        local prefix
        prefix=$(echo "$local_storage_ip" | cut -d. -f1-3)
        echo "${prefix}.${remote_node}"
    fi
}

rail_port() {
    echo $((PORT_BASE + $1))
}

pick_bw_tool() {
    case "$VERB" in
        write) echo ib_write_bw ;;
        read)  echo ib_read_bw ;;
        send)  echo ib_send_bw ;;
        *) err "VERB must be write, read, or send"; exit 1 ;;
    esac
}

preflight() {
    require_cmd ip
    require_cmd rdma
    local tool
    tool=$(pick_bw_tool)
    require_cmd "$tool"

    if "$tool" --help 2>&1 | grep -q -- '--bind_source_ip'; then
        USE_BIND_SOURCE=1
        log "$tool supports --bind_source_ip; source-IP pinning enabled."
    else
        USE_BIND_SOURCE=0
        log "$tool does not support --bind_source_ip; using kernel routing."
    fi
}

check_rail_local() {
    local rail="$1" node="$2"
    local ip netdev rdmadev
    ip=$(rail_ip_local "$rail" "$node") || return 1
    netdev=$(rail_netdev "$rail")
    rdmadev=$(rail_rdmadev "$rail")

    # 1. 检查网络接口是否存在
    if ! ip -o link show dev "$netdev" >/dev/null 2>&1; then
        err "Netdev ${netdev} does not exist"
        return 1
    fi

    # 2. 检查网络接口上是否有 IP
    if ! ip -4 -o addr show dev "$netdev" | grep -qw "$ip"; then
        err "${netdev} does not have IPv4 ${ip}"
        return 1
    fi

    # 3. 检查 RDMA 设备是否存在
    if ! rdma dev 2>/dev/null | grep -qw "$rdmadev"; then
        err "RDMA device ${rdmadev} not found in 'rdma dev'"
        return 1
    fi

    log "rail${rail} ($( [ $rail -eq 4 ] && echo "Storage" || echo "Compute" )): netdev=${netdev}, rdmadev=${rdmadev}, ip=${ip}, port=$(rail_port "$rail")"
}

server_one() {
    local rail="$1" node="$2"
    local ip dev port tool outfile
    ip=$(rail_ip_local "$rail" "$node")
    dev=$(rail_rdmadev "$rail")
    port=$(rail_port "$rail")
    tool=$(pick_bw_tool)
    outfile="${LOG_DIR}/server_rail${rail}_${ip}.log"

    : > "$outfile"
    log "SERVER rail${rail}: ${dev} ${ip}:${port} -> ${tool}"

    local cmd=(
        "$tool"
        -d "$dev"
        -R
        -p "$port"
        -s "$MSG_SIZE"
        -q "$QP"
        -t "$TX_DEPTH"
        -D "$DURATION"
    )
    if (( USE_BIND_SOURCE )); then
        cmd+=(--bind_source_ip "$ip")
    fi

    "${cmd[@]}" >> "$outfile" 2>&1 &
    SERVER_PIDS+=($!)
}

run_client_one() {
    local rail="$1" local_node="$2" remote_node="$3"
    local src_ip dst_ip netdev rdmadev port tool outfile rc
    src_ip=$(rail_ip_local "$rail" "$local_node")
    dst_ip=$(rail_ip_remote "$rail" "$local_node" "$remote_node")
    netdev=$(rail_netdev "$rail")
    rdmadev=$(rail_rdmadev "$rail")
    port=$(rail_port "$rail")
    tool=$(pick_bw_tool)
    outfile="${LOG_DIR}/client_rail${rail}_${src_ip}_to_${dst_ip}_q${QP}.log"

    log "CLIENT rail${rail}: ${src_ip} -> ${dst_ip}, netdev=${netdev}, rdmadev=${rdmadev}, port=${port}, QP=${QP}, size=${MSG_SIZE}"

    # 1. 检查路由方向
    local route_line route_dev route_src
    route_line=$(ip -4 route get "$dst_ip" 2>/dev/null || true)
    route_dev=$(awk '{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}' <<< "$route_line")
    route_src=$(awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}' <<< "$route_line")

    if [[ "$route_dev" != "$netdev" ]]; then
        err "rail${rail}: route to ${dst_ip} uses dev=${route_dev:-<none>}, expected ${netdev}"
        err "route: ${route_line:-<no route>}"
        return 1
    fi

    # 2. 基础网络 ICMP 测试
    if ! ping -c 2 -W 1 -I "$netdev" "$dst_ip" >/dev/null 2>&1; then
        log "WARN rail${rail}: ICMP ping via ${netdev} to ${dst_ip} failed/skipped; continuing with RDMA-CM test."
    fi

    # 3. 压测命令
    local cmd=(
        "$tool"
        -d "$rdmadev"
        -R
        -p "$port"
        -s "$MSG_SIZE"
        -q "$QP"
        -t "$TX_DEPTH"
        -D "$DURATION"
    )
    if (( USE_BIND_SOURCE )); then
        cmd+=(--bind_source_ip "$src_ip")
    fi
    cmd+=("$dst_ip")

    set +e
    "${cmd[@]}" 2>&1 | tee "$outfile"
    rc=${PIPESTATUS[0]}
    set -e

    echo
    echo "========== rail${rail} ($( [ $rail -eq 4 ] && echo "Storage" || echo "Compute" )) result =========="
    if [[ $rc -eq 0 ]]; then
        grep -E 'BW average|BW peak|Gb/sec|Gbit|Mpps|MB/sec' "$outfile" | tail -5 || true
        echo "log: $outfile"
    else
        echo "FAILED (exit=$rc)"
        tail -30 "$outfile" || true
    fi
    echo "========================================="
    echo
    return "$rc"
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
    local node="$1"
    valid_node_id "$node" || { err "node_id must be 1..254"; exit 2; }
    mkdir -p "$LOG_DIR"
    preflight

    trap cleanup_server INT TERM EXIT

    log "Starting 5 rail listeners (4 Compute + 1 Storage) on node ${node}"
    log "Config: msg=${MSG_SIZE}, qp=${QP}, tx_depth=${TX_DEPTH}, duration=${DURATION}, verb=${VERB}"

    local rail
    for ((rail=0; rail<RAIL_COUNT; rail++)); do
        check_rail_local "$rail" "$node" || exit 1
        server_one "$rail" "$node"
    done

    log "All 5 listeners started. Keep this terminal running while client tests execute."
    wait
}

client_mode() {
    local local_node="$1" remote_node="$2"
    valid_node_id "$local_node" || { err "local_node_id must be 1..254"; exit 2; }
    valid_node_id "$remote_node" || { err "remote_node_id must be 1..254"; exit 2; }
    mkdir -p "$LOG_DIR"
    preflight

    log "Starting Client parallel testing (4 Compute + 1 Storage): Node $local_node -> Node $remote_node"

    # 本地网卡检查
    local rail
    for ((rail=0; rail<RAIL_COUNT; rail++)); do
        check_rail_local "$rail" "$local_node" || exit 1
    done

    # 并发拉起 5 个 Rail 打满测试
    local client_pids=()
    for ((rail=0; rail<RAIL_COUNT; rail++)); do
        run_client_one "$rail" "$local_node" "$remote_node" &
        client_pids+=($!)
    done

    local failed=0
    for pid in "${client_pids[@]}"; do
        wait "$pid" || failed=$((failed + 1))
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
            if [[ $# -ne 1 ]]; then usage; exit 1; fi
            server_mode "$1"
            ;;
        client)
            if [[ $# -ne 2 ]]; then usage; exit 1; fi
            client_mode "$1" "$2"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
