#!/usr/bin/python

from __future__ import print_function
import subprocess
import argparse
import time
import re

##################
# CONSTANTS
##################
g_vlan_list = [610, 241, 242, 243]
g_spine_vxlan_vlan = 490
g_spine_vxlan = 4900

##################
# CMDS
##################
pre_cmds = """
vrouter-ospf6-remove vrouter-name hmplabpsq-we60100-vrouter nic eth0.610
vrouter-ospf-remove vrouter-name hmplabpsq-we60100-vrouter network 104.255.62.40 
vrouter-interface-remove vrouter-name hmplabpsq-we60100-vrouter nic eth0.610

vrouter-ospf6-remove vrouter-name hmplabpsq-we60200-vrouter nic eth1.610
vrouter-ospf-remove vrouter-name hmplabpsq-we60200-vrouter network 104.255.62.41 
vrouter-interface-remove vrouter-name hmplabpsq-we60200-vrouter nic eth1.610

vrouter-ospf6-remove vrouter-name hmplabpsq-we50100-vrouter nic eth2.610
vrouter-ospf-remove vrouter-name hmplabpsq-we50100-vrouter network 104.255.62.44 
vrouter-interface-remove vrouter-name hmplabpsq-we50100-vrouter nic eth2.610

vrouter-ospf6-remove vrouter-name hmplabpsq-we50200-vrouter nic eth3.610
vrouter-ospf-remove vrouter-name hmplabpsq-we50200-vrouter network 104.255.62.45 
vrouter-interface-remove vrouter-name hmplabpsq-we50200-vrouter nic eth3.610

vrouter-ospf6-remove vrouter-name hmplabpsq-we50300-vrouter nic eth4.610
vrouter-ospf-remove vrouter-name hmplabpsq-we50300-vrouter network 104.255.62.46
vrouter-interface-remove vrouter-name hmplabpsq-we50300-vrouter nic eth4.610

vrouter-ospf6-remove vrouter-name hmplabpsq-we50400-vrouter nic eth5.610
vrouter-ospf-remove vrouter-name hmplabpsq-we50400-vrouter network 104.255.62.47
vrouter-interface-remove vrouter-name hmplabpsq-we50400-vrouter nic eth5.610
 
vrouter-ospf6-remove vrouter-name hmplabpsq-we50500-vrouter nic eth6.610
vrouter-ospf-remove vrouter-name hmplabpsq-we50500-vrouter network 104.255.62.48 
vrouter-interface-remove vrouter-name hmplabpsq-we50500-vrouter nic eth6.610
 
vrouter-ospf6-remove vrouter-name hmplabpsq-we50600-vrouter nic eth7.610
vrouter-ospf-remove vrouter-name hmplabpsq-we50600-vrouter network 104.255.62.49 
vrouter-interface-remove vrouter-name hmplabpsq-we50600-vrouter nic eth7.610
"""

post_cmds = """
vrouter-interface-add vrouter-name hmplabpsq-we60100-vrouter ip 104.255.62.40/27 ip2 2620:0000:167F:b010::10/64 vlan 610
vrouter-interface-add vrouter-name hmplabpsq-we60200-vrouter ip 104.255.62.41/27 ip2 2620:0000:167F:b010::11/64 vlan 610
vrouter-interface-add vrouter-name hmplabpsq-we50100-vrouter ip 104.255.62.44/27 ip2 2620:0000:167F:b010::14/64 vlan 610
vrouter-interface-add vrouter-name hmplabpsq-we50200-vrouter ip 104.255.62.45/27 ip2 2620:0000:167F:b010::15/64 vlan 610
vrouter-interface-add vrouter-name hmplabpsq-we50300-vrouter ip 104.255.62.46/27 ip2 2620:0000:167F:b010::16/64 vlan 610
vrouter-interface-add vrouter-name hmplabpsq-we50400-vrouter ip 104.255.62.47/27 ip2 2620:0000:167F:b010::17/64 vlan 610
vrouter-interface-add vrouter-name hmplabpsq-we50500-vrouter ip 104.255.62.48/27 ip2 2620:0000:167F:b010::18/64 vlan 610
vrouter-interface-add vrouter-name hmplabpsq-we50600-vrouter ip 104.255.62.49/27 ip2 2620:0000:167F:b010::19/64 vlan 610

switch hmplabpsq-we50500 vrouter-bgp-network-remove vrouter-name hmplabpsq-we50500-vrouter ip 104.255.62.40/27
switch hmplabpsq-we50500 vrouter-bgp-network-remove vrouter-name hmplabpsq-we50500-vrouter ip 2620:0000:167F:b010::10/64

switch hmplabpsq-we50600 vrouter-bgp-network-remove vrouter-name hmplabpsq-we50600-vrouter ip 104.255.62.40/27
switch hmplabpsq-we50600 vrouter-bgp-network-remove vrouter-name hmplabpsq-we50600-vrouter ip 2620:0000:167F:b010::10/64

vrouter-loopback-interface-add vrouter-name hmplabpsq-we60100-vrouter ip 2620:0000:167F:b000::10
vrouter-loopback-interface-add vrouter-name hmplabpsq-we60200-vrouter ip 2620:0000:167F:b000::11
vrouter-loopback-interface-add vrouter-name hmplabpsq-we50100-vrouter ip 2620:0000:167F:b000::14
vrouter-loopback-interface-add vrouter-name hmplabpsq-we50200-vrouter ip 2620:0000:167F:b000::15
vrouter-loopback-interface-add vrouter-name hmplabpsq-we50300-vrouter ip 2620:0000:167F:b000::16
vrouter-loopback-interface-add vrouter-name hmplabpsq-we50400-vrouter ip 2620:0000:167F:b000::17
vrouter-loopback-interface-add vrouter-name hmplabpsq-we50500-vrouter ip 2620:0000:167F:b000::18
vrouter-loopback-interface-add vrouter-name hmplabpsq-we50600-vrouter ip 2620:0000:167F:b000::19
"""

##################
# ARGUMENT PARSING
##################
parser = argparse.ArgumentParser(description='VXLAN pair creator')
parser.add_argument(
    '--spine1',
    help='Name of Spine1',
    required=True
)
parser.add_argument(
    '--ip1',
    help='Spine1 IP',
    required=True
)
parser.add_argument(
    '--spine2',
    help='Name of Spine2',
    required=True
)
parser.add_argument(
    '--ip2',
    help='Spine2 IP',
    required=True
)
parser.add_argument(
    '--show-only',
    help='will show commands it will run',
    action='store_true',
    required=False
)
args = vars(parser.parse_args())

g_ip1 = args["ip1"]
g_ip2 = args["ip2"]
g_spine1 = args["spine1"]
g_spine2 = args["spine2"]
show_only = args["show_only"]

g_spine_ip = [(g_spine1, g_ip1), (g_spine2, g_ip2)]

##################
# VALIDATIONs
##################

def validate_ipv4(ip):
    V4_RE = re.compile(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.)"
                         "{3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])"
                         "(\/([0-9]|[1-2][0-9]|3[0-2]))$")
    if V4_RE.match(ip):
        return True
    return False

if not validate_ipv4(args['ip1']):
    print("Invalid IP1 address format")
    exit(0)
if not validate_ipv4(args['ip2']):
    print("Invalid IP2 address format")
    exit(0)

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
if g_spine1 not in g_fab_nodes:
    print("Incorrect spine name %s" % sw)
    exit(0)
if g_spine2 not in g_fab_nodes:
    print("Incorrect spine name %s" % sw)
    exit(0)

######### Running PRE Commands ####################
for cmd in pre_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(5)
print("")

######### TUNNELS BETWEEN LEAF & SPINE ############
for spine_ip in g_spine_ip:
    spine, ip = spine_ip[0], spine_ip[1] 
    print("Create VLAN %s on spine: %s" % (g_spine_vxlan_vlan, spine))
    run_cmd("switch %s vlan-create id %s scope local" % (spine,
                g_spine_vxlan_vlan))
    sleep(2)
    print("Creating interface on spine: %s, ip: %s, vlan: %s" % (spine, ip,
                g_spine_vxlan_vlan))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter ip %s vlan %s" % (
                spine, ip, g_spine_vxlan_vlan))
print("")

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
    if vip not in g_vip_list:
        g_vip_list[vip] = vrname[:-8]

for spine_ip in g_spine_ip:
    spine, ip = spine_ip[0], spine_ip[1]
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
        print("Adding vxlan id %s" % g_spine_vxlan)
        run_cmd("switch %s tunnel-vxlan-add name %s vxlan %s" % (
            leaf_sw, tun_name, g_spine_vxlan))
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
        print("Adding vxlan id %s" % g_spine_vxlan)
        run_cmd("switch %s tunnel-vxlan-add name %s vxlan %s" % (
            spine, tun_name, g_spine_vxlan))

    print("")
print("Modifying all trunk to have vxlan loopback port as 47")
run_cmd("switch \* trunk-modify name vxlan-loopback-trunk ports 47")
sleep(3)
print("")

######### Configuration for all VLANs #############
for vlan in g_vlan_list:
    print("Deleting vlan: %s" % vlan)
    run_cmd("vlan-delete id %s" % vlan)
    sleep(2)
print("")

for vlan in g_vlan_list:
    vxlan = vlan * 10
    print("Creating local scoped vlan %s with vxlan %s on "
          "hmplabpsq-we60100" % (vlan, vxlan))
    run_cmd("switch hmplabpsq-we60100 vlan-create id %s scope local ports 47 "
            "vxlan %s" % (vlan, vxlan))
    sleep(2)
    print("Creating local scoped vlan %s with vxlan %s on "
          "hmplabpsq-we60200" % (vlan, vxlan))
    run_cmd("switch hmplabpsq-we60200 vlan-create id %s scope local ports 47 "
            "vxlan %s" % (vlan, vxlan))
    sleep(2)
    print("Creating cluster scoped vlan %s with vxlan %s on "
          "hmplabpsq-we50100" % (vlan, vxlan))
    run_cmd("switch hmplabpsq-we50100 vlan-create id %s scope cluster ports 47 "
            "vxlan %s" % (vlan, vxlan))
    sleep(2)
    print("Creating cluster scoped vlan %s with vxlan %s on "
          "hmplabpsq-we50300" % (vlan, vxlan))
    run_cmd("switch hmplabpsq-we50300 vlan-create id %s scope cluster ports 47 "
            "vxlan %s" % (vlan, vxlan))
    sleep(2)
    print("Creating cluster scoped vlan %s with vxlan %s on "
          "hmplabpsq-we50500" % (vlan, vxlan))
    run_cmd("switch hmplabpsq-we50500 vlan-create id %s scope cluster ports 47 "
            "vxlan %s" % (vlan, vxlan))
    print("")

    tun_info = run_cmd("tunnel-show format switch,name parsable-delim ,")
    for itun in tun_info:
        if not itun:
            print("Unable to find tunnels")
            exit(0)
        sw, tun_name = itun.split(',')
        print("Adding vxlan %s to tunnel %s on switch %s" % (
                vxlan, tun_name, sw))
        run_cmd("switch %s tunnel-vxlan-add name %s vxlan %s" % (
                sw, tun_name, vxlan))
        sleep(1)
    print("")

######### Running POST Commands ####################
for cmd in post_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(5)
print("")

################################################
print("DONE")
################################################
