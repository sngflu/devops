#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Creating cloud-init ISO ===${NC}"

# Create cloud-init directory
mkdir -p cloud-init

cat > cloud-init/user-data <<EOF
#cloud-config
hostname: docker-host
fqdn: docker-host.local

users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: sudo
    shell: /bin/bash
    lock_passwd: false
    # Password is 'ubuntu'
    passwd: \$6\$NMlawbmy7G7DhYsh\$BNjj0YdvB07M1mN3FKxkAVLszBM2s6qCwS35UUcMHVv4DHhS8bh8NFCfHjsJ3mwuEfIlQYMh9jRdSEV6w2UKn/

# Enable password authentication for SSH
ssh_pwauth: true

package_update: true
package_upgrade: true

packages:
  - openssh-server
  - python3
  - python3-pip
  - avahi-daemon
  - apt-transport-https
  - ca-certificates
  - curl
  - software-properties-common
  - docker.io
  - docker-compose

write_files:
  - path: /etc/apt/apt.conf.d/90wait
    content: |
      APT::Get::Update::InteractiveMode "false";
      APT::Get::Install::InteractiveMode "false";
  - path: /etc/ssh/sshd_config.d/allow_password_auth.conf
    content: |
      PasswordAuthentication yes
      ChallengeResponseAuthentication no

runcmd:
  # Configure Docker
  - systemctl enable docker
  - systemctl start docker
  - usermod -aG docker ubuntu
  # Restart SSH with new configuration
  - systemctl restart sshd
  # Create a file to signal that setup is complete
  - touch /var/lib/cloud/instance/setup-complete

final_message: "The system is finally up, after \$UPTIME seconds"
EOF

cat > cloud-init/meta-data <<EOF
instance-id: docker-host
local-hostname: docker-host
EOF

cat > cloud-init/network-config <<EOF
version: 2
ethernets:
  enp0s3:
    dhcp4: true
  enp0s8:
    dhcp4: false
    addresses: [192.168.56.10/24]
EOF

# Generate cloud-init ISO
if command -v cloud-localds &> /dev/null; then
    cloud-localds -v --network-config=cloud-init/network-config cloud-init/cloud-init.iso cloud-init/user-data cloud-init/meta-data
else
    echo -e "${RED}cloud-localds not found, installing...${NC}"
    sudo apt-get update && sudo apt-get install -y cloud-image-utils
    cloud-localds -v --network-config=cloud-init/network-config cloud-init/cloud-init.iso cloud-init/user-data cloud-init/meta-data
fi

echo -e "${GREEN}Cloud-init ISO created at cloud-init/cloud-init.iso${NC}"

# Clean SSH known_hosts entry for the VM to avoid SSH errors
if [ -f ~/.ssh/known_hosts ]; then
    echo -e "${YELLOW}Removing old SSH host key...${NC}"
    ssh-keygen -f ~/.ssh/known_hosts -R "[127.0.0.1]:2222" 2>/dev/null || true
fi

# Check if VM exists before trying to attach ISO
if VBoxManage list vms | grep -q "lab2-docker-vm"; then
    echo -e "${YELLOW}Attaching cloud-init ISO to VM...${NC}"
    VBoxManage storageattach lab2-docker-vm --storagectl "IDE Controller" --port 1 --device 0 --type dvddrive --medium $(pwd)/cloud-init/cloud-init.iso
    echo -e "${GREEN}Cloud-init ISO attached to VM${NC}"
else
    echo -e "${YELLOW}VM not found. ISO created but not attached.${NC}"
    echo -e "${YELLOW}Run setup.sh to create and configure the VM.${NC}"
fi 