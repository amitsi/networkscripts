from __future__ import print_function
from string import Template
import subprocess
import argparse
import time
import sys

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Single Cmds')
parser.add_argument(
    '-p', '--port',
    help='vxlan-loopback-trunk port',
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

g_lport = args['port']
if not g_lport.isdigit():
    print("VXLAN Loopback port is incorrect")
    exit(0)

g_inter_cmd_sleep = 3

inband_setup_cmds = """
switch hmplabpsq-we50600 trunk-modify name vxlan-loopback-trunk ports $loport
switch hmplabpsq-we50600 vlan-create id 610 vxlan 6100 scope local description inbandMGMT
switch hmplabpsq-we50600 fabric-local-modify vlan 610
switch hmplabpsq-we50600 switch-setup-modify in-band-ip 104.255.62.49/27 in-band-ip6 2620:0:167f:b010::19/64
"""

vlan490_intfs_cmds = """ 
vrouter-modify name hmplabpsq-we50600-vrouter hw-vrrp-id 15
vrouter-interface-add vrouter-name hmplabpsq-we50600-vrouter nic eth10.490 ip 104.255.61.147/29 vlan 490 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50600-vrouter nic eth11.490 ip 104.255.61.145/29 vlan 490 vrrp-id 15 vrrp-primary eth10.490 vrrp-priority 109 mtu 9216 
vrouter-interface-config-add vrouter-name hmplabpsq-we50600-vrouter nic eth10.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50600-vrouter nic eth11.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default

vrouter-ospf-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.144/29 ospf-area 0
"""
 
snmp_cmds = """ 
switch hmplabpsq-we50600 admin-service-modify if mgmt ssh nfs no-web no-web-ssl snmp net-api icmp
switch hmplabpsq-we50600 admin-service-modify if data ssh nfs no-web no-web-ssl snmp net-api icmp
switch hmplabpsq-we50600 admin-session-timeout-modify timeout 3600s
switch hmplabpsq-we50600 snmp-user-create user-name VINETro auth priv auth-password baseball priv-password baseball
switch hmplabpsq-we50600 snmp-user-create user-name VINETrw auth priv auth-password football priv-password football
switch hmplabpsq-we50600 snmp-community-create community-string baseball community-type read-only
switch hmplabpsq-we50600 snmp-community-create community-string football community-type read-write
switch hmplabpsq-we50600 snmp-trap-sink-create community baseball type TRAP_TYPE_V2_INFORM dest-host 104.254.40.101
switch hmplabpsq-we50600 snmp-vacm-create user-type rouser user-name __nvOS_internal no-auth no-priv
switch hmplabpsq-we50600 snmp-vacm-create user-type rouser user-name VINETro auth priv
switch hmplabpsq-we50600 snmp-vacm-create user-type rwuser user-name VINETrw auth priv
switch hmplabpsq-we50600 role-create name abcd scope local
"""

bgp_cmds = """
vrouter-modify name hmplabpsq-we50600-vrouter bgp-as 65542 ospf-default-information always
vrouter-interface-add vrouter-name hmplabpsq-we50600-vrouter ip 104.255.61.67/31 ip2 2620:0:167f:b001::36/126 l3-port 1 mtu 9216 
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.10/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.9/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.8/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.7/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.6/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.5/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.2/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.1/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::10/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::11/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::14/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::15/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::16/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::17/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::18/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::19/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b015::/64
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::38/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::3c/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::40/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::44/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::48/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::4c/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::50/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::54/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::58/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::5c/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::60/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b001::64/126
vrouter-bgp-add vrouter-name hmplabpsq-we50600-vrouter neighbor 104.255.61.66 remote-as 65020 next-hop-self soft-reconfig-inbound
vrouter-bgp-add vrouter-name hmplabpsq-we50600-vrouter neighbor 104.255.61.90 remote-as 65542
vrouter-bgp-add vrouter-name hmplabpsq-we50600-vrouter neighbor 2620:0:167f:b001::35 remote-as 65020 multi-protocol ipv6-unicast
vrouter-ospf-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.8/32 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.78/31 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.88/31 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.90/31 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.144/29 ospf-area 0
vrouter-pim-config-modify vrouter-name hmplabpsq-we50600-vrouter query-interval 10 querier-timeout 30
"""

trunk_vlag_cmds = """
switch hmplabpsq-we50600 trunk-create name 506tocisco ports 2,3

switch hmplabpsq-we50600 vlan-port-add ports 129 vlan-id 241
switch hmplabpsq-we50600 vlan-port-add ports 129 vlan-id 242
switch hmplabpsq-we50600 vlan-port-add ports 129 vlan-id 243
switch hmplabpsq-we50600  vlan-port-add ports 129 vlan-id 610
"""

cpu_class_cmds = """
switch hmplabpsq-we50600 port-cos-bw-modify cos 0 port 1-104 min-bw-guarantee 68
switch hmplabpsq-we50600 port-cos-bw-modify cos 4 port 1-104 min-bw-guarantee 8
switch hmplabpsq-we50600 port-cos-bw-modify cos 5 port 1-104 min-bw-guarantee 20
switch hmplabpsq-we50600 port-cos-bw-modify cos 6 port 1-104 min-bw-guarantee 4
"""

def run_cmd(cmd):
    m_cmd = ("cli --quiet --script-password --no-login-prompt -e "
             "--user network-admin:test123 %s" % cmd)
    if show_only and "-show" not in cmd:
        print("### " + cmd)
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

def _print(msg, end="nl", must_show=False):
    if not msg:
        print("")
        sys.stdout.flush()
    elif must_show or not show_only:
        if end == "nl":
            print(msg)
        else:
            print(msg, end='')
        sys.stdout.flush()
    else:
        pass
################

######### Running Commands ####################
_print("### Setting up Inband IP v4/v6 on vlan 490...", must_show=True)
_print("### =========================================", must_show=True)
inbandcmd = Template(inband_setup_cmds)
inband_setup_cmds = inbandcmd.substitute(loport=g_lport)
for cmd in inband_setup_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")

_print("### Setting vrouter interfaces on vlan 490...", must_show=True)
_print("### =========================================", must_show=True)
for cmd in vlan490_intfs_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")

_print("### Setting up SNMP...", must_show=True)
_print("### ==================", must_show=True)
for cmd in snmp_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")

_print("### Setting up BGP...", must_show=True)
_print("### ==================", must_show=True)
for cmd in bgp_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")

_print("### Setting up trunk/vLAG...", must_show=True)
_print("### ========================", must_show=True)
for cmd in trunk_vlag_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")

_print("### Setting up CPU Classes...", must_show=True)
_print("### =========================", must_show=True)
for cmd in cpu_class_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")
