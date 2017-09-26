#!/usr/bin/python

""" PN VRRP Creation """

from __future__ import print_function
import subprocess
import argparse
import time

##################
# Constants
##################
g_vrrp_id = 15
g_prim_vrrp_pri = 110
g_sec_vrrp_pri = 109

##################
# ARGUMENT PARSING
##################
parser = argparse.ArgumentParser(description='VXLAN pair creator')
parser.add_argument(
    '-x', '--pair1',
    help='pair of switches separated by comma',
    required=True
)
parser.add_argument(
    '-y', '--pair2',
    help='pair of switches separated by comma',
    required=True
)
parser.add_argument(
    '-v', '--vlan',
    help='VLAN ID',
    required=True
)
parser.add_argument(
    '-V', '--vxlan',
    help='VXLAN ID',
    required=True
)
parser.add_argument(
    '-l', '--lo',
    help='loopback port',
    required=True
)
args = vars(parser.parse_args())

##################
# VALIDATIONs
##################
g_pair1 = [i.strip() for i in args['pair1'].split(',')]
if len(g_pair1) != 2:
    print("Incorrect number of switches specified. There must be 2 switches")
    exit(0)

g_pair2 = [i.strip() for i in args['pair2'].split(',')]
if len(g_pair1) != 2:
    print("Incorrect number of switches specified. There must be 2 switches")
    exit(0)

g_vlan_id = args['vlan']
if not g_vlan_id.isdigit() or int(g_vlan_id) not in range(0, 4095):
    print("VLAN ID is incorrect")
    exit(0)

g_vxlan_id = args['vxlan']
if not g_vxlan_id.isdigit() or int(g_vxlan_id) not in range(0, 16777215):
    print("VXLAN ID is incorrect")
    exit(0)

g_lport = args['lo']
if not g_lport.isdigit():
    print("Loopback port is incorrect")
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
for sw in g_pair1:
    if sw not in g_fab_nodes:
        print("Incorrect switch name %s" % sw)
        exit(0)

# Validate switch list
for sw in g_pair2:
    if sw not in g_fab_nodes:
        print("Incorrect switch name %s" % sw)
        exit(0)

print("Modifying vlan %s with vxlan %s of switch %s" % (
    g_vlan_id, g_vxlan_id, g_pair1[0]))
run_cmd("switch %s vlan-modify id %s vxlan %s" % (
    g_pair1[0], g_vlan_id, g_vxlan_id))
print("")

# Validate routers
g_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,")
for vinfo in vrouter_info:
    if not vinfo:
        print("No vrouters found")
        exit(0)
    vr_name = vinfo
    g_vrouters.append(vr_name)
for sw in g_pair1:
    if sw+"-vrouter" not in g_vrouters:
        print("Vrouter %s-vrouter doesn't exist" % sw)
        exit(0)
for sw in g_pair2:
    if sw+"-vrouter" not in g_vrouters:
        print("Vrouter %s-vrouter doesn't exist" % sw)
        exit(0)

#####################VIP INFO###################

vip_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter "
                   "vlan %s is-vip true format ip parsable-delim ," % (
                       g_pair1[0], g_vlan_id))
g_vip1 = ''
for vipinfo in vip_info:
    if not vipinfo:
        print("No VIP interface exists")
        exit(0)
    g_vip1 = vipinfo.split(',')[1].split('/')[0]
    break

vip_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter "
                   "vlan %s is-vip true format ip parsable-delim ," % (
                       g_pair2[0], g_vlan_id))
g_vip2 = ''
for vipinfo in vip_info:
    if not vipinfo:
        print("No VIP interface exists")
        exit(0)
    g_vip2 = vipinfo.split(',')[1].split('/')[0]
    break

######################PAIR-1####################
tunnel_name = "%s-pair-to-%s-pair" % (g_pair1[0], g_pair2[0])
print("Creating tunnel %s from VIP1: %s "
      "to VIP2: %s" % (tunnel_name, g_vip1, g_vip2))
run_cmd("switch %s tunnel-create name %s scope cluster "
        "local-ip %s remote-ip %s vrouter-name %s-vrouter "
        "peer-vrouter-name %s-vrouter" % (g_pair1[0], tunnel_name,
                                          g_vip1, g_vip2,
                                          g_pair1[0], g_pair1[1]))
time.sleep(2)
print("")

print("Adding vxlan id %s" % g_vxlan_id)
run_cmd("switch %s tunnel-vxlan-add name %s vxlan %s" % (
    g_pair1[0], tunnel_name, g_vxlan_id))
print("")

print("Adding port %s to vxlan-loopback-trunk" % g_lport)
run_cmd("trunk-modify name vxlan-loopback-trunk ports %s" % g_lport)
time.sleep(2)
print("")

######################PAIR-2####################
tunnel_name = "%s-pair-to-%s-pair" % (g_pair2[0], g_pair1[0])
print("Creating tunnel %s from VIP1: %s to VIP2: %s" % (tunnel_name,
                                                        g_vip2, g_vip1))
run_cmd("switch %s tunnel-create name %s scope cluster "
        "local-ip %s remote-ip %s vrouter-name %s-vrouter "
        "peer-vrouter-name %s-vrouter" % (g_pair2[0], tunnel_name,
                                          g_vip2, g_vip1,
                                          g_pair2[0], g_pair2[1]))
time.sleep(2)
print("")

print("Adding vxlan id %s" % g_vxlan_id)
run_cmd("switch %s tunnel-vxlan-add name %s vxlan %s" % (
    g_pair2[0], tunnel_name, g_vxlan_id))
print("")

print("Adding port %s to vxlan-loopback-trunk" % g_lport)
run_cmd("trunk-modify name vxlan-loopback-trunk ports %s" % g_lport)
time.sleep(2)
print("")

################################################
print("DONE")
################################################
