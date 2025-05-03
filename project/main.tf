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
