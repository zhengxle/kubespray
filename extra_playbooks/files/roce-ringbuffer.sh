#!/bin/bash
LOG_FILE="/var/log/roce-ringbuffer.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "===== 开始设置 Ring Buffer ====="

DEVS="ens55f0np0 ens55f1np1 ens50f0np0 ens50f1np1
      enp96s0f0np0 enp96s0f1np1 enp75s0f0np0 enp75s0f1np1
      ens1f0np0 ens1f1np1"

for dev in $DEVS; do
    if [ ! -d "/sys/class/net/$dev" ]; then
        log "  [SKIP] $dev 不存在"
        continue
    fi
    if ethtool -G "$dev" rx 2047 tx 2047 rx-jumbo 8191 2>/dev/null; then
        log "  [OK] $dev Ring Buffer -> 2047/2047/8191"
    else
        # 尝试只设置 RX/TX，不动 Jumbo
        ethtool -G "$dev" rx 2047 tx 2047 2>/dev/null \
            && log "  [OK] $dev Ring Buffer -> 2047/2047 (Jumbo 保持原值)" \
            || log "  [WARN] $dev Ring Buffer 设置失败"
    fi
    rx=$(ethtool -g "$dev" 2>/dev/null | grep -A4 "Current" | grep "^RX:" | awk '{print $2}')
    tx=$(ethtool -g "$dev" 2>/dev/null | grep -A4 "Current" | grep "^TX:" | awk '{print $2}')
    log "       $dev 当前值: RX=$rx TX=$tx"
done

log "===== Ring Buffer 设置完成 ====="
