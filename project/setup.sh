#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check for required tools
check_dependencies() {
    echo -e "${YELLOW}Checking for required tools...${NC}"
    
    # Check for VirtualBox
    if ! command -v VBoxManage &> /dev/null; then
        echo -e "${RED}VirtualBox is not installed. Please install VirtualBox first.${NC}"
        exit 1
    fi
    
    # Check for sshpass
    if ! command -v sshpass &> /dev/null; then
        echo -e "${RED}sshpass is not installed. Installing...${NC}"
        sudo apt-get update && sudo apt-get install -y sshpass
    fi
    
    # Check for cloud-image-utils
    if ! command -v cloud-localds &> /dev/null; then
        echo -e "${RED}cloud-image-utils not found, installing...${NC}"
        sudo apt-get update && sudo apt-get install -y cloud-image-utils
    fi
    
    # Check for qemu-img
    if ! command -v qemu-img &> /dev/null; then
        echo -e "${RED}qemu-img not found, installing...${NC}"
        sudo apt-get update && sudo apt-get install -y qemu-utils
    fi
    
    # Check for Ubuntu cloud image
    if [ ! -f "ubuntu-20.04-server-cloudimg-amd64.img" ]; then
        echo -e "${YELLOW}Downloading Ubuntu 20.04 cloud image...${NC}"
        wget https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img -O ubuntu-20.04-server-cloudimg-amd64.img
    fi
}

# Clean up function
cleanup() {
    echo -e "${YELLOW}=== Cleaning up any existing resources ===${NC}"
    
    # Check if VM exists and remove it
    if VBoxManage list vms | grep -q "lab2-docker-vm"; then
        echo -e "${YELLOW}Removing existing VM...${NC}"
        VBoxManage controlvm lab2-docker-vm poweroff 2>/dev/null || true
        sleep 5
        VBoxManage unregistervm lab2-docker-vm --delete 2>/dev/null || true
        sleep 5
    fi
    
    # Remove any temporary files
    rm -rf ~/VirtualBox\ VMs/lab2-docker-vm 2>/dev/null || true
    rm -f ~/VirtualBox\ VMs/lab2-docker-vm-disk.vdi 2>/dev/null || true
    
    # Clean SSH known_hosts entry for the VM to avoid SSH errors
    if [ -f ~/.ssh/known_hosts ]; then
        echo -e "${YELLOW}Removing old SSH host key...${NC}"
        ssh-keygen -f ~/.ssh/known_hosts -R "[127.0.0.1]:2222" 2>/dev/null || true
    fi
    
    # Create SSH config file for this VM
    mkdir -p ~/.ssh
    cat > ~/.ssh/config <<EOF
Host lab2-docker-vm
    HostName 127.0.0.1
    Port 2222
    User ubuntu
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    PasswordAuthentication yes
    IdentitiesOnly yes
    LogLevel ERROR
EOF
    chmod 600 ~/.ssh/config
    
    echo -e "${GREEN}Cleanup complete${NC}"
}

# Create cloud-init ISO
create_cloud_init_iso() {
    echo -e "${YELLOW}=== Creating cloud-init ISO ===${NC}"
    
    # Create cloud-init directory
    mkdir -p cloud-init
    
    # Create user-data
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

# Don't install packages during first boot, we'll do it in runcmd
package_update: false
package_upgrade: false

# Minimal packages for SSH and Python
packages:
  - openssh-server
  - python3

write_files:
  - path: /etc/apt/apt.conf.d/90wait
    content: |
      APT::Get::Update::InteractiveMode "false";
      APT::Get::Install::InteractiveMode "false";
  - path: /etc/ssh/sshd_config.d/allow_password_auth.conf
    content: |
      PasswordAuthentication yes
      ChallengeResponseAuthentication no
  - path: /etc/systemd/resolved.conf
    content: |
      [Resolve]
      DNS=8.8.8.8 8.8.4.4
      FallbackDNS=1.1.1.1 9.9.9.9
      #Domains=
      #LLMNR=no
      #MulticastDNS=no
      #DNSSEC=no
      #DNSOverTLS=no
      #Cache=no-negative
      #DNSStubListener=yes
      #ReadEtcHosts=yes

runcmd:
  # Для уверенности, что мы не прерываем установку пакетов
  - systemctl mask apt-daily.service apt-daily-upgrade.service
  - systemctl stop unattended-upgrades.service || true
  - systemctl mask unattended-upgrades.service
  
  # Установка дополнительных пакетов
  - apt-get update
  - apt-get install -y python3-pip avahi-daemon apt-transport-https ca-certificates curl software-properties-common

  # Установка Docker отдельно
  - apt-get install -y docker.io docker-compose
  
  # Restart systemd-resolved to apply DNS changes
  - systemctl restart systemd-resolved
  
  # Configure Docker
  - systemctl enable docker
  - systemctl start docker
  - usermod -aG docker ubuntu
  
  # Restart SSH with new configuration
  - systemctl restart sshd
  
  # Create a file to signal that setup is complete
  - touch /var/lib/cloud/instance/setup-complete
  
  # Create a file to indicate apt process completion
  - touch /var/lib/cloud/instance/apt-complete

final_message: "The system is finally up, after \$UPTIME seconds"
EOF

    # Create meta-data
    cat > cloud-init/meta-data <<EOF
instance-id: docker-host
local-hostname: docker-host
EOF

    # Create network-config
    cat > cloud-init/network-config <<EOF
version: 2
ethernets:
  enp0s3:
    dhcp4: true
    nameservers:
      addresses: [8.8.8.8, 8.8.4.4]
  enp0s8:
    dhcp4: false
    addresses: [192.168.56.10/24]
    nameservers:
      addresses: [8.8.8.8, 8.8.4.4]
EOF

    # Generate cloud-init ISO
    cloud-localds -v --network-config=cloud-init/network-config cloud-init/cloud-init.iso cloud-init/user-data cloud-init/meta-data
    
    echo -e "${GREEN}Cloud-init ISO created at cloud-init/cloud-init.iso${NC}"
}

# Prepare bootable disk image
prepare_disk_image() {
    echo -e "${YELLOW}=== Preparing bootable disk image ===${NC}"
    
    # Create a directory for VirtualBox VMs if it doesn't exist
    mkdir -p ~/VirtualBox\ VMs/
    
    # Get image format
    local format=$(qemu-img info ubuntu-20.04-server-cloudimg-amd64.img | grep "file format" | awk '{print $3}')
    echo -e "${GREEN}Detected cloud image format: ${format}${NC}"
    
    # Convert cloud image to VDI format
    echo -e "${GREEN}Converting cloud image to VDI format...${NC}"
    qemu-img convert -f $format -O vdi ubuntu-20.04-server-cloudimg-amd64.img ~/VirtualBox\ VMs/lab2-docker-vm-disk.vdi
    
    # Resize the disk (20GB)
    echo -e "${GREEN}Resizing disk to 20GB...${NC}"
    VBoxManage modifymedium disk ~/VirtualBox\ VMs/lab2-docker-vm-disk.vdi --resize 20480
}

# Create VM
create_vm() {
    echo -e "${YELLOW}=== Setting up Docker VM with VirtualBox ===${NC}"
    
    # Check if host-only network exists
    if ! VBoxManage list hostonlyifs | grep -q "vboxnet0"; then
        echo -e "${YELLOW}Creating host-only network...${NC}"
        VBoxManage hostonlyif create
        VBoxManage hostonlyif ipconfig vboxnet0 --ip 192.168.56.1 --netmask 255.255.255.0
    fi
    
    # Create VM
    echo -e "${GREEN}Creating VM...${NC}"
    VBoxManage createvm --name lab2-docker-vm --ostype Ubuntu_64 --register
    
    # Configure VM
    echo -e "${GREEN}Configuring VM...${NC}"
    VBoxManage modifyvm lab2-docker-vm --memory 2048 --cpus 2
    VBoxManage modifyvm lab2-docker-vm --nic1 nat
    VBoxManage modifyvm lab2-docker-vm --nic2 hostonly --hostonlyadapter2 vboxnet0
    VBoxManage modifyvm lab2-docker-vm --boot1 disk --boot2 dvd --boot3 none --boot4 none
    
    # Configure storage controllers
    echo -e "${GREEN}Setting up VM storage...${NC}"
    VBoxManage storagectl lab2-docker-vm --name "SATA Controller" --add sata --controller IntelAhci
    VBoxManage storagectl lab2-docker-vm --name "IDE Controller" --add ide --controller PIIX4
    
    # Attach disk and cloud-init ISO
    VBoxManage storageattach lab2-docker-vm --storagectl "SATA Controller" --port 0 --device 0 --type hdd --medium ~/VirtualBox\ VMs/lab2-docker-vm-disk.vdi
    VBoxManage storageattach lab2-docker-vm --storagectl "IDE Controller" --port 0 --device 0 --type dvddrive --medium "$(pwd)/cloud-init/cloud-init.iso"
    
    # Set up port forwarding
    echo -e "${GREEN}Setting up port forwarding...${NC}"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "ssh,tcp,127.0.0.1,2222,,22"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "frontend,tcp,127.0.0.1,5173,,5173"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "backend,tcp,127.0.0.1,5174,,5174"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "pgadmin,tcp,127.0.0.1,5050,,5050"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "minio-api,tcp,127.0.0.1,9000,,9000"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "minio-console,tcp,127.0.0.1,9001,,9001"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "http,tcp,127.0.0.1,8080,,80"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "api,tcp,127.0.0.1,8000,,8000"
    VBoxManage modifyvm lab2-docker-vm --natpf1 "alt-http,tcp,127.0.0.1,8081,,8080"
}

# Create Terraform configuration
create_terraform_config() {
    echo -e "${GREEN}Creating Terraform configuration...${NC}"
    cat > main.tf <<EOF
# Terraform configuration to maintain VM metadata
# This file documents the VM configuration using Terraform syntax
# The VM itself is created using VBoxManage commands

terraform {
  required_providers {
    null = {
      source = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

resource "null_resource" "documentation" {
  triggers = {
    vm_name = "lab2-docker-vm"
    cpus = "2"
    memory = "2048"
    os_type = "Ubuntu_64"
    ssh_port = "2222"
    hostonly_ip = "192.168.56.10"
  }
}

output "connection_info" {
  value = "VM can be accessed via SSH at: ssh -p 2222 ubuntu@127.0.0.1"
}

output "services" {
  value = {
    frontend = "http://127.0.0.1:5173"
    backend = "http://127.0.0.1:5174"
    pgadmin = "http://127.0.0.1:5050"
    minio_console = "http://127.0.0.1:9001"
    minio_api = "http://127.0.0.1:9000"
  }
}
EOF
}

# Create Ansible inventory
create_ansible_inventory() {
    echo -e "${GREEN}Creating Ansible inventory...${NC}"
    mkdir -p ansible
    cat > ansible/inventory.ini <<EOF
[servers]
docker_host ansible_host=127.0.0.1 ansible_port=2222

[servers:vars]
ansible_user=ubuntu
ansible_ssh_pass=ubuntu
ansible_become=yes
ansible_become_method=sudo
ansible_become_pass=ubuntu
ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR'
EOF
}

# Start VM function
start_vm() {
    echo -e "${GREEN}Starting VM...${NC}"
    VBoxManage startvm lab2-docker-vm --type headless
    
    echo -e "${YELLOW}Waiting for VM to boot and cloud-init to complete...${NC}"
    
    # Wait for SSH to become available
    echo -e "${YELLOW}Waiting for SSH connection...${NC}"
    for i in {1..120}; do
        if nc -z 127.0.0.1 2222 >/dev/null 2>&1; then
            echo -e "${GREEN}SSH is available!${NC}"
            break
        fi
        echo -n "."
        sleep 5
    done
    
    # Give additional time for cloud-init to complete
    echo -e "${YELLOW}Waiting for cloud-init to complete...${NC}"
    sleep 30
}

# Wait for VM to be fully ready
wait_for_vm_ready() {
    echo -e "${YELLOW}Checking if VM is fully set up...${NC}"
    
    for i in {1..10}; do
        if sshpass -p "ubuntu" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 2222 ubuntu@127.0.0.1 "test -f /var/lib/cloud/instance/setup-complete"; then
            echo -e "${GREEN}VM is fully set up and ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 10
    done
    
    echo -e "${RED}Timed out waiting for VM to be fully set up. Continuing anyway...${NC}"
}

# Test Ansible connection
test_ansible_connection() {
    echo -e "${YELLOW}Testing Ansible connection...${NC}"
    ANSIBLE_HOST_KEY_CHECKING=False ansible docker_host -i ansible/inventory.ini -m ping
}

# Main function
main() {
    check_dependencies
    cleanup
    create_cloud_init_iso
    prepare_disk_image
    create_vm
    create_terraform_config
    create_ansible_inventory
    start_vm
    wait_for_vm_ready
    test_ansible_connection
    
    # Дождемся, пока apt-get завершит свою работу
    echo -e "${YELLOW}Waiting for apt processes to finish...${NC}"
    for i in {1..15}; do
        if sshpass -p "ubuntu" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 2222 ubuntu@127.0.0.1 "test -f /var/lib/cloud/instance/apt-complete"; then
            echo -e "${GREEN}Package management system is free!${NC}"
            break
        fi
        echo -n "."
        sleep 10
    done
    
    # Полное обновление системы перед перезагрузкой
    echo -e "${YELLOW}Upgrading all system packages...${NC}"
    sshpass -p "ubuntu" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 2222 ubuntu@127.0.0.1 "sudo apt-get update && sudo apt-get upgrade -y"
    
    # Перезагрузим VM перед запуском Ansible
    echo -e "${YELLOW}Rebooting VM before Ansible deployment...${NC}"
    sshpass -p "ubuntu" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 2222 ubuntu@127.0.0.1 "sudo reboot" || true
    
    # Подождем пока VM перезагрузится и SSH снова станет доступен
    echo -e "${YELLOW}Waiting for VM to reboot...${NC}"
    sleep 20
    for i in {1..20}; do
        if nc -z 127.0.0.1 2222 >/dev/null 2>&1; then
            echo -e "${GREEN}VM rebooted successfully and SSH is available!${NC}"
            # Дополнительная пауза для полной загрузки системы
            sleep 10
            break
        fi
        echo -n "."
        sleep 5
    done
    
    # Исправляем прерванную установку пакетов
    echo -e "${YELLOW}Fixing interrupted package installation...${NC}"
    sshpass -p "ubuntu" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 2222 ubuntu@127.0.0.1 "sudo dpkg --configure -a"
    
    # Дополнительная проверка с очисткой кэшей apt
    echo -e "${YELLOW}Cleaning apt caches and updating packages...${NC}"
    sshpass -p "ubuntu" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 2222 ubuntu@127.0.0.1 "sudo apt-get clean && sudo apt-get update"
    
    # Обновим все пакеты
    echo -e "${YELLOW}Making sure all packages are properly installed...${NC}"
    sshpass -p "ubuntu" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 2222 ubuntu@127.0.0.1 "sudo apt-get install -f -y"
    
    # Автоматически запускаем Ansible плейбук для деплоя проекта
    echo -e "${YELLOW}Automatically deploying project with Ansible...${NC}"
    ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i ansible/inventory.ini ansible/deploy_project.yml -vvv
    
    echo -e "${GREEN}=== VM Setup Complete ===${NC}"
    echo -e "${GREEN}Your VM is now fully set up and project is deployed!${NC}"
    echo -e "${YELLOW}To SSH into your VM:${NC}"
    echo "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 2222 ubuntu@127.0.0.1"
}

# Run the main function
main 