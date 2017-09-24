#!/usr/bin/python

""" PN VRRP Creation """

from __future__ import print_function
import subprocess
import argparse
import time
import re

##################
# Constants
##################
g_vrrp_id = 15
g_prim_vrrp_pri = 110
g_sec_vrrp_pri = 109

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='VRRP creator')
parser.add_argument(
    '-s', '--switch',
    help='list of switches separated by comma. Switch1 will become primary',
    required=True
)
parser.add_argument(
    '-v', '--vlan',
    help='VLAN ID',
    required=True
)
parser.add_argument(
    '-i', '--ip',
    help='IP address in CIDR notation',
    required=True
)
args = vars(parser.parse_args())

##################
# VALIDATIONs
##################
g_switch_list = [i.strip() for i in args['switch'].split(',')]
if len(g_switch_list) != 2:
    print("Incorrect number of switches specified. There must be 2 switches")
    exit(0)

g_ip_range = args['ip']
cidr_pat = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])(\/([0-9]|[1-2][0-9]|3[0-2]))$"
if not re.match(cidr_pat, g_ip_range):
    print("Incorrect IP address format. It should be in CIDR notation")
    exit(0)

g_vlan_id = args['vlan']
if not g_vlan_id.isdigit() or int(g_vlan_id) not in range(0,4095):
    print("VLAN ID is incorrect")
    exit(0)

##################

def run_cmd(cmd):
    cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % cmd)
        exit(0)

def get_ips(ip):
    ip_addr = ip.split('.')
    fourth_octet = ip_addr[3].split('/')
    subnet = fourth_octet[1]
    static_ip = ip_addr[0] + '.' + ip_addr[1] + '.' + ip_addr[2] + '.'
    ip1 = static_ip + '1' + '/' + subnet
    ip2 = static_ip + '2' + '/' + subnet
    ip3 = static_ip + '3' + '/' + subnet
    return(ip1,ip2,ip3)

##################

# Get list of fabric nodes
g_fab_nodes = []
fab_info = run_cmd("fabric-node-show format name parsable-delim ,")
for finfo in fab_info:
    if not finfo:
        print("No fabric output")
        exit(0)
    sw_name = finfo
    g_fab_nodes.append(sw_name)

# Validate switch list
for sw in g_switch_list:
    if sw not in g_fab_nodes:
        print("Incorrect switch name %s" % sw)
        exit(0)

# Validate routers
g_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,")
for vinfo in vrouter_info:
    if not vinfo:
        print("No vrouters found")
        exit(0)
    vr_name = vinfo
    g_vrouters.append(vr_name)
for sw in g_switch_list:
    if sw+"-vrouter" not in g_vrouters:
        print("Vrouter %s-vrouter doesn't exist" % sw)
        exit(0)

# Set VRRP ID for vrouters
print("Set VRRP ID %s for router %s-vrouter" % (g_vrrp_id,g_switch_list[0]))
run_cmd("vrouter-modify name %s-vrouter hw-vrrp-id %s" % (g_switch_list[0],g_vrrp_id))
print("Set VRRP ID %s for router %s-vrouter" % (g_vrrp_id,g_switch_list[1]))
run_cmd("vrouter-modify name %s-vrouter hw-vrrp-id %s" % (g_switch_list[1],g_vrrp_id))
time.sleep(2)
print("")

run_cmd("vlan-create id %s scope fabric" % g_vlan_id)
print("Created VLAN = %s" % g_vlan_id)
time.sleep(2)
print("")

vip,ip1,ip2 = get_ips(g_ip_range)
print("Creating VRRP interfaces using:")
print("    VIP=%s" % vip)
print("    Primary IP=%s" % ip1)
print("    Secondary IP=%s" % ip2)

print("")
print("Creating interface with sw: %s, ip: %s, vlan-id: %s" % (g_switch_list[0],ip1,g_vlan_id))
run_cmd("vrouter-interface-add vrouter-name %s-vrouter ip %s vlan %s if data" % (g_switch_list[0],ip1,g_vlan_id))
intf_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter ip %s vlan %s format nic parsable-delim ," % (g_switch_list[0],ip1,g_vlan_id))
for intf in intf_info:
    if not intf:
        print("No router interface exist")
        exit(0)
    pintf_index = intf.split(',')[1]
    break
time.sleep(2)
print("")

print("Setting vrrp-master interface with sw: %s, vip: %s, vlan-id: %s, vrrp-id: %s, vrrp-priority: %s" % (g_switch_list[0],vip,g_vlan_id,g_vrrp_id,g_prim_vrrp_pri))
run_cmd("vrouter-interface-add vrouter-name %s-vrouter ip %s vlan %s if data vrrp-id %s vrrp-primary %s vrrp-priority %s" % (g_switch_list[0],vip,g_vlan_id,g_vrrp_id,pintf_index,g_prim_vrrp_pri))
time.sleep(2)
print("")

print("Creating interface with sw: %s, ip: %s, vlan-id: %s" % (g_switch_list[1],ip2,g_vlan_id))
run_cmd("vrouter-interface-add vrouter-name %s-vrouter ip %s vlan %s if data" % (g_switch_list[1],ip2,g_vlan_id))
intf_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter ip %s vlan %s format nic parsable-delim ," % (g_switch_list[1],ip2,g_vlan_id))
for intf in intf_info:
    if not intf:
        print("No router interface exist")
        exit(0)
    sintf_index = intf.split(',')[1]
    break
time.sleep(2)
print("")

print("Setting vrrp-slave interface with sw: %s, vip: %s, vlan-id: %s, vrrp-id: %s, vrrp-priority: %s" % (g_switch_list[1],vip,g_vlan_id,g_vrrp_id,g_sec_vrrp_pri))
run_cmd("vrouter-interface-add vrouter-name %s-vrouter ip %s vlan %s if data vrrp-id %s vrrp-primary %s vrrp-priority %s" % (g_switch_list[1],vip,g_vlan_id,g_vrrp_id,sintf_index,g_sec_vrrp_pri))
time.sleep(2)
print("")

print("DONE")
