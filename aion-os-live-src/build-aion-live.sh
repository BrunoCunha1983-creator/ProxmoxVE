#!/usr/bin/env bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive
ROOT=/work/aion-os-live-src
WORK=/tmp/aion-live
OUT=/work/dist
rm -rf "$WORK"; mkdir -p "$WORK" "$OUT"; cd "$WORK"
lb config --mode debian --distribution trixie --architectures amd64 --binary-images iso-hybrid --archive-areas 'main contrib' --firmware-chroot false --firmware-binary false --debian-installer live --bootappend-live 'boot=live components hostname=aion-live username=aion' --iso-volume 'AION_LIVE_01'
mkdir -p config/package-lists config/archives config/includes.chroot/opt/aion/web config/includes.chroot/opt/aion config/includes.chroot/etc/systemd/system config/hooks/live
curl -fsSL https://enterprise.proxmox.com/debian/proxmox-release-trixie.gpg -o config/archives/proxmox.key.chroot
cp config/archives/proxmox.key.chroot config/archives/proxmox.key.binary
cat > config/archives/proxmox.list.chroot <<'EOF'
deb http://download.proxmox.com/debian/pve trixie pve-no-subscription
EOF
cp config/archives/proxmox.list.chroot config/archives/proxmox.list.binary
cat > config/package-lists/aion.list.chroot <<'EOF'
proxmox-ve
proxmox-default-kernel
ifupdown2
open-iscsi
chrony
openssh-server
curl
ca-certificates
openssl
smartmontools
zfsutils-linux
python3
python3-fastapi
python3-uvicorn
jq
live-boot
live-config
EOF
install -m755 "$ROOT/aion.py" config/includes.chroot/opt/aion/aion.py
install -m755 "$ROOT/maintenance.py" config/includes.chroot/opt/aion/maintenance.py
install -m644 "$ROOT/index.html" config/includes.chroot/opt/aion/web/index.html
cat > config/includes.chroot/etc/systemd/system/aion-web.service <<'EOF'
[Unit]
Description=AION native management core and WebGUI
After=network-online.target pve-cluster.service
Wants=network-online.target
[Service]
Type=simple
User=root
Environment=AION_USER=admin
Environment=AION_PASSWORD=aion-test
ExecStart=/usr/bin/python3 -m uvicorn aion:app --app-dir /opt/aion --host 0.0.0.0 --port 8006 --ssl-keyfile /etc/aion/key.pem --ssl-certfile /etc/aion/cert.pem
Restart=always
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF
cat > config/includes.chroot/etc/systemd/system/aion-maintenance.service <<'EOF'
[Unit]
Description=AION autonomous 48-hour maintenance and log review
After=pve-cluster.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/aion/maintenance.py
EOF
cat > config/includes.chroot/etc/systemd/system/aion-maintenance.timer <<'EOF'
[Unit]
Description=AION autonomous maintenance timer
[Timer]
OnBootSec=15min
OnUnitActiveSec=48h
Persistent=true
RandomizedDelaySec=10min
[Install]
WantedBy=timers.target
EOF
cat > config/includes.chroot/etc/systemd/system/aion-firstboot.service <<'EOF'
[Unit]
Description=AION first boot preparation
Before=aion-web.service
After=network.target
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/aion-firstboot
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
mkdir -p config/includes.chroot/usr/local/sbin
cat > config/includes.chroot/usr/local/sbin/aion-firstboot <<'EOF'
#!/bin/sh
set -eu
mkdir -p /etc/aion /var/lib/aion
[ -s /etc/aion/key.pem ] || openssl req -x509 -newkey rsa:3072 -nodes -days 365 -subj '/CN=AION Server OS' -keyout /etc/aion/key.pem -out /etc/aion/cert.pem
hostnamectl set-hostname aion-live 2>/dev/null || true
grep -q 'aion-live' /etc/hosts || echo '127.0.1.1 aion-live.local aion-live' >> /etc/hosts
systemctl disable --now pveproxy.service 2>/dev/null || true
systemctl mask pveproxy.service 2>/dev/null || true
printf '\nAION Server OS Live\nWebGUI: https://<this-PC-IP>:8006\nLogin: admin / aion-test\n\n' > /etc/issue
EOF
chmod +x config/includes.chroot/usr/local/sbin/aion-firstboot
cat > config/hooks/live/0900-aion-enable.hook.chroot <<'EOF'
#!/bin/sh
set -eu
mkdir -p /etc/aion /var/lib/aion
systemctl enable aion-firstboot.service aion-web.service aion-maintenance.timer ssh.service
EOF
chmod +x config/hooks/live/0900-aion-enable.hook.chroot
lb build
ISO=$(find . -maxdepth 1 -name '*.iso' -print -quit); test -n "$ISO"
cp "$ISO" "$OUT/aion-server-os-live-0.1-amd64.iso"
sha256sum "$OUT/aion-server-os-live-0.1-amd64.iso" > "$OUT/aion-server-os-live-0.1-amd64.iso.sha256"
