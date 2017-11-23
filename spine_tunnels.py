#!/usr/bin/python

from __future__ import print_function
import subprocess
import argparse
import time

##################
# CONSTANTS
##################
g_spine_vxlan_vlan = 490

##################
# ARGUMENT PARSING
##################
parser = argparse.ArgumentParser(description='VXLAN pair creator')
parser.add_argument(
    '--spine',
    help='list of spines',
    required=True
)
parser.add_argument(
    '--show-only',
    help='will show commands it will run',
    action='store_true',
    required=False
)
args = vars(parser.parse_args())

show_only = args["show_only"]

##################

def run_cmd(cmd):
    m_cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    if show_only and "-show" not in cmd:
        print(">>> " + cmd)
        return
    try:
        proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % m_cmd)
        exit(0)

def sleep(sec):
    if not show_only:
        time.sleep(sec)

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

# Validate spines
g_spine_list = [i.strip() for i in args['spine'].split(',')]
for spine in g_spine_list:
    if spine not in g_fab_nodes:
        print("Incorrect spine name %s" % spine)
        exit(0)

######### TUNNELS BETWEEN LEAF & SPINE ############
intf_info = run_cmd("vrouter-interface-show vlan %s format ip "
                    "parsable-delim ," % (g_spine_vxlan_vlan))
g_spine_svis = {}
for intf in intf_info:
    if not intf:
        print("No interfaces exist on vlan 490")
        exit(0)
    vrname,ip = intf.split(',')
    if len(ip) > 18:
        continue
    if vrname[:-8] in g_spine_list: 
        g_spine_svis[vrname[:-8]] = ip

if not g_spine_svis:
    print("Unable to find any spine IPv4 SVIs on vlan: %s" % g_spine_vxlan_vlan)
    exit(0)

vip_info = run_cmd("vrouter-interface-show vlan %s is-vip true format ip "
                   "parsable-delim ," % g_spine_vxlan_vlan)
g_vip_list = {}
for vipinfo in vip_info:
    if not vipinfo:
        print("No VIP interface exists")
        exit(0)
    vrname,vip = vipinfo.split(',')
    vip = vip.split('/')[0]
    if len(vip) > 15:
        # Skip IPv6 Addresses
        continue
    sw_name = vrname[:-8]
    if vip not in g_vip_list:
        g_vip_list[vip] = sw_name
    else:
        if sw_name < g_vip_list[vip]:
            g_vip_list[vip] = sw_name

for spine in g_spine_svis:
    ip = g_spine_svis[spine]
    ip = ip.split('/')[0]
    print("Configuring VXLAN tunnels for Spine: %s" % spine)
    for vip in g_vip_list:
        leaf_sw = g_vip_list[vip]
        tun_name = leaf_sw + "-pair-to-" + spine
        print("Creating tunnel %s from VIP: %s to IP: %s" % (
                tun_name, vip, ip))
        run_cmd("switch %s tunnel-create name %s scope cluster "
                "local-ip %s remote-ip %s vrouter-name %s-vrouter "
                "peer-vrouter-name %s-vrouter" % (
                    leaf_sw, tun_name, vip,
                    ip, leaf_sw, spine))
        sleep(2)
        tun_name = spine + "-to-" + leaf_sw + "-pair"
        print("Creating tunnel %s from IP: %s to VIP: %s" % (
                tun_name, ip, vip))
        run_cmd("switch %s tunnel-create name %s scope local "
                "local-ip %s remote-ip %s vrouter-name %s-vrouter "
                "peer-vrouter-name %s-vrouter" % (
                    spine, tun_name, ip,
                    vip, spine, leaf_sw))
        sleep(2)

    print("")

################################################
print("DONE")
################################################
