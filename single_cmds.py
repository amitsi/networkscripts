from __future__ import print_function
import subprocess
import argparse
import time
import sys

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Single Cmds')
parser.add_argument(
    '--show-only',
    help='will show commands it will run',
    action='store_true',
    required=False
)
args = vars(parser.parse_args())

show_only = args["show_only"]

g_inter_cmd_sleep = 3

inband_setup_cmds = """
switch \* vlan-create id 610 vxlan 6100 scope local description inbandMGMT
switch \* fabric-local-modify vlan 610
switch hmplabpsq-we60100 switch-setup-modify in-band-ip 104.255.62.40/27 in-band-ip6 2620:0:167f:b010::10/64
switch hmplabpsq-we60200 switch-setup-modify in-band-ip 104.255.62.41/27 in-band-ip6 2620:0:167f:b010::11/64
switch hmplabpsq-we50100 switch-setup-modify in-band-ip 104.255.62.44/27 in-band-ip6 2620:0:167f:b010::14/64
switch hmplabpsq-we50200 switch-setup-modify in-band-ip 104.255.62.45/27 in-band-ip6 2620:0:167f:b010::15/64
switch hmplabpsq-we50300 switch-setup-modify in-band-ip 104.255.62.46/27 in-band-ip6 2620:0:167f:b010::16/64
switch hmplabpsq-we50400 switch-setup-modify in-band-ip 104.255.62.47/27 in-band-ip6 2620:0:167f:b010::17/64
switch hmplabpsq-we50500 switch-setup-modify in-band-ip 104.255.62.48/27 in-band-ip6 2620:0:167f:b010::18/64
switch hmplabpsq-we50600 switch-setup-modify in-band-ip 104.255.62.49/27 in-band-ip6 2620:0:167f:b010::19/64
"""

vlan490_intfs_cmds = """ 
vlan-create id 490 scope fabric description vlan-490
vrouter-interface-add vrouter-name hmplabpsq-we60100-vrouter nic eth12.490 ip 10.9.9.1/24 vlan 490 
vrouter-interface-add vrouter-name hmplabpsq-we60200-vrouter nic eth13.490 ip 10.9.10.1/24 vlan 490 
vrouter-interface-add vrouter-name hmplabpsq-we50100-vrouter nic eth0.490 ip 104.255.61.130/29 vlan 490 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50100-vrouter nic eth1.490 ip 104.255.61.129/29 vlan 490 vrrp-id 15 vrrp-primary eth0.490 vrrp-priority 110 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50200-vrouter nic eth2.490 ip 104.255.61.131/29 vlan 490 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50200-vrouter nic eth3.490 ip 104.255.61.129/29 vlan 490 vrrp-id 15 vrrp-primary eth2.490 vrrp-priority 109 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50300-vrouter nic eth4.490 ip 104.255.61.138/29 vlan 490 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50300-vrouter nic eth5.490 ip 104.255.61.137/29 vlan 490 vrrp-id 15 vrrp-primary eth4.490 vrrp-priority 110 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50400-vrouter nic eth6.490 ip 104.255.61.139/29 vlan 490 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50400-vrouter nic eth7.490 ip 104.255.61.137/29 vlan 490 vrrp-id 15 vrrp-primary eth6.490 vrrp-priority 109 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50500-vrouter nic eth8.490 ip 104.255.61.146/29 vlan 490 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50500-vrouter nic eth9.490 ip 104.255.61.145/29 vlan 490 vrrp-id 15 vrrp-primary eth8.490 vrrp-priority 110 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50600-vrouter nic eth10.490 ip 104.255.61.147/29 vlan 490 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50600-vrouter nic eth11.490 ip 104.255.61.145/29 vlan 490 vrrp-id 15 vrrp-primary eth10.490 vrrp-priority 109 mtu 9216 
vrouter-interface-config-add vrouter-name hmplabpsq-we50100-vrouter nic eth0.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50100-vrouter nic eth1.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50200-vrouter nic eth2.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50200-vrouter nic eth3.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50300-vrouter nic eth4.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50300-vrouter nic eth5.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50400-vrouter nic eth6.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50400-vrouter nic eth7.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50500-vrouter nic eth8.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50500-vrouter nic eth9.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50600-vrouter nic eth10.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default
vrouter-interface-config-add vrouter-name hmplabpsq-we50600-vrouter nic eth11.490 ospf-dead-interval 40 ospf-passive-if ospf-bfd default

vrouter-ospf-add vrouter-name hmplabpsq-we60100-vrouter network 10.9.9.0/24 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we60200-vrouter network 10.9.10.0/24 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50100-vrouter network 104.255.61.128/29 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50200-vrouter network 104.255.61.128/29 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50300-vrouter network 104.255.61.136/29 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50400-vrouter network 104.255.61.136/29 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.144/29 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.144/29 ospf-area 0
"""
 
vlan244_intfs_cmds = """
vlan-create id 244 scope fabric
vrouter-interface-add vrouter-name hmplabpsq-we50100-vrouter nic eth0.244 ip 104.255.62.162/27 ip2 2620:0:167f:b015::2/64 vlan 244 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50100-vrouter nic eth1.244 ip 104.255.62.161/27 vlan 244 vrrp-id 15 vrrp-primary eth0.244 vrrp-priority 110 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50100-vrouter nic eth4.244 ip 2620:0:167f:b015::1/64 vlan 244 vrrp-id 15 vrrp-primary eth0.244 vrrp-priority 110 
vrouter-interface-add vrouter-name hmplabpsq-we50200-vrouter nic eth2.244 ip 104.255.62.163/27 ip2 2620:0:167f:b015::3/64 vlan 244 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50200-vrouter nic eth3.244 ip 104.255.62.161/27 vlan 244 vrrp-id 15 vrrp-primary eth2.244 vrrp-priority 109 mtu 9216 
vrouter-interface-add vrouter-name hmplabpsq-we50200-vrouter nic eth5.244 ip 2620:0:167f:b015::1/64 vlan 244 vrrp-id 15 vrrp-primary eth2.244 vrrp-priority 109 
vrouter-ospf6-add vrouter-name hmplabpsq-we50100-vrouter nic eth4.244 ospf6-area 0.0.0.0
vrouter-ospf6-add vrouter-name hmplabpsq-we50200-vrouter nic eth5.244 ospf6-area 0.0.0.0
vrouter-ospf-add vrouter-name hmplabpsq-we50100-vrouter network 104.255.62.160/27 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50200-vrouter network 104.255.62.160/27 ospf-area 0
"""

tunnel_setup_cmds = """ 
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vrouter-name hmplabpsq-we50200-vrouter peer-vrouter-name hmplabpsq-we50100-vrouter local-ip 104.255.61.129 remote-ip 104.255.61.137
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vrouter-name hmplabpsq-we50100-vrouter peer-vrouter-name hmplabpsq-we50200-vrouter local-ip 104.255.61.129 remote-ip 104.255.61.137
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we50500-pair vrouter-name hmplabpsq-we50100-vrouter peer-vrouter-name hmplabpsq-we50200-vrouter local-ip 104.255.61.129 remote-ip 104.255.61.145
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we50500-pair vrouter-name hmplabpsq-we50200-vrouter peer-vrouter-name hmplabpsq-we50100-vrouter local-ip 104.255.61.129 remote-ip 104.255.61.145
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we60100 vrouter-name hmplabpsq-we50100-vrouter peer-vrouter-name hmplabpsq-we60100-vrouter local-ip 104.255.61.129 remote-ip 10.9.9.1
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we60100 vrouter-name hmplabpsq-we60100-vrouter peer-vrouter-name hmplabpsq-we50100-vrouter local-ip 104.255.61.129 remote-ip 10.9.9.1
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we60200 vrouter-name hmplabpsq-we50100-vrouter peer-vrouter-name hmplabpsq-we60200-vrouter local-ip 104.255.61.129 remote-ip 10.9.10.1
tunnel-create scope cluster name hmplabpsq-we50100-pair-to-hmplabpsq-we60200 vrouter-name hmplabpsq-we60200-vrouter peer-vrouter-name hmplabpsq-we50100-vrouter local-ip 104.255.61.129 remote-ip 10.9.10.1
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vrouter-name hmplabpsq-we50400-vrouter peer-vrouter-name hmplabpsq-we50300-vrouter local-ip 104.255.61.137 remote-ip 104.255.61.129
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vrouter-name hmplabpsq-we50300-vrouter peer-vrouter-name hmplabpsq-we50400-vrouter local-ip 104.255.61.137 remote-ip 104.255.61.129
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vrouter-name hmplabpsq-we50300-vrouter peer-vrouter-name hmplabpsq-we50400-vrouter local-ip 104.255.61.137 remote-ip 104.255.61.145
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vrouter-name hmplabpsq-we50400-vrouter peer-vrouter-name hmplabpsq-we50300-vrouter local-ip 104.255.61.137 remote-ip 104.255.61.145
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we60100 vrouter-name hmplabpsq-we50300-vrouter peer-vrouter-name hmplabpsq-we60100-vrouter local-ip 104.255.61.137 remote-ip 10.9.9.1
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we60100 vrouter-name hmplabpsq-we60100-vrouter peer-vrouter-name hmplabpsq-we50300-vrouter local-ip 104.255.61.137 remote-ip 10.9.9.1
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we60200 vrouter-name hmplabpsq-we50300-vrouter peer-vrouter-name hmplabpsq-we60200-vrouter local-ip 104.255.61.137 remote-ip 10.9.10.1
tunnel-create scope cluster name hmplabpsq-we50300-pair-to-hmplabpsq-we60200 vrouter-name hmplabpsq-we60200-vrouter peer-vrouter-name hmplabpsq-we50300-vrouter local-ip 104.255.61.137 remote-ip 10.9.10.1
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vrouter-name hmplabpsq-we50600-vrouter peer-vrouter-name hmplabpsq-we50500-vrouter local-ip 104.255.61.145 remote-ip 104.255.61.129
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vrouter-name hmplabpsq-we50500-vrouter peer-vrouter-name hmplabpsq-we50600-vrouter local-ip 104.255.61.145 remote-ip 104.255.61.129
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vrouter-name hmplabpsq-we50600-vrouter peer-vrouter-name hmplabpsq-we50500-vrouter local-ip 104.255.61.145 remote-ip 104.255.61.137
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vrouter-name hmplabpsq-we50500-vrouter peer-vrouter-name hmplabpsq-we50600-vrouter local-ip 104.255.61.145 remote-ip 104.255.61.137
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we60100 vrouter-name hmplabpsq-we50500-vrouter peer-vrouter-name hmplabpsq-we60100-vrouter local-ip 104.255.61.145 remote-ip 10.9.9.1
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we60100 vrouter-name hmplabpsq-we60100-vrouter peer-vrouter-name hmplabpsq-we50500-vrouter local-ip 104.255.61.145 remote-ip 10.9.9.1
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we60200 vrouter-name hmplabpsq-we50500-vrouter peer-vrouter-name hmplabpsq-we60200-vrouter local-ip 104.255.61.145 remote-ip 10.9.10.1
tunnel-create scope cluster name hmplabpsq-we50500-pair-to-hmplabpsq-we60200 vrouter-name hmplabpsq-we60200-vrouter peer-vrouter-name hmplabpsq-we50500-vrouter local-ip 104.255.61.145 remote-ip 10.9.10.1
tunnel-create scope local name hmplabpsq-we60100-to-hmplabpsq-we50100-pair vrouter-name hmplabpsq-we60100-vrouter local-ip 10.9.9.1 remote-ip 104.255.61.129
tunnel-create scope local name hmplabpsq-we60100-to-hmplabpsq-we50300-pair vrouter-name hmplabpsq-we60100-vrouter local-ip 10.9.9.1 remote-ip 104.255.61.137
tunnel-create scope local name hmplabpsq-we60100-to-hmplabpsq-we50500-pair vrouter-name hmplabpsq-we60100-vrouter local-ip 10.9.9.1 remote-ip 104.255.61.145
tunnel-create scope local name hmplabpsq-we60200-to-hmplabpsq-we50100-pair vrouter-name hmplabpsq-we60200-vrouter local-ip 10.9.10.1 remote-ip 104.255.61.129
tunnel-create scope local name hmplabpsq-we60200-to-hmplabpsq-we50300-pair vrouter-name hmplabpsq-we60200-vrouter local-ip 10.9.10.1 remote-ip 104.255.61.137
tunnel-create scope local name hmplabpsq-we60200-to-hmplabpsq-we50500-pair vrouter-name hmplabpsq-we60200-vrouter local-ip 10.9.10.1 remote-ip 104.255.61.145

tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we60100 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we60100 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we60200 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we60200 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we60100 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we60100 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we60200 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we60200 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we60100 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we60100 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we60200 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we60200 vxlan 6100
tunnel-vxlan-add name hmplabpsq-we60100-to-hmplabpsq-we50100-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we60100-to-hmplabpsq-we50300-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we60100-to-hmplabpsq-we50500-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we60200-to-hmplabpsq-we50100-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we60200-to-hmplabpsq-we50300-pair vxlan 6100
tunnel-vxlan-add name hmplabpsq-we60200-to-hmplabpsq-we50500-pair vxlan 6100

tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 4210
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 4210

tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 4220
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 4220

tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50100-pair-to-hmplabpsq-we50300-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50100-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50300-pair-to-hmplabpsq-we50500-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50100-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 4230
tunnel-vxlan-add name hmplabpsq-we50500-pair-to-hmplabpsq-we50300-pair vxlan 4230
"""
 
syslog_cmds = """
admin-syslog-create name vzsyslog scope fabric host 146.13.191.77 message-format structured
"""
 
snmp_cmds = """ 
admin-service-modify if mgmt ssh nfs no-web no-web-ssl snmp net-api icmp
admin-service-modify if data ssh nfs no-web no-web-ssl snmp net-api icmp
admin-session-timeout-modify timeout 3600s
snmp-user-create user-name VINETro auth priv auth-password baseball priv-password baseball
snmp-user-create user-name VINETrw auth priv auth-password football priv-password football
snmp-community-create community-string baseball community-type read-only
snmp-community-create community-string football community-type read-write
snmp-trap-sink-create community baseball type TRAP_TYPE_V2_INFORM dest-host 104.254.40.101
snmp-vacm-create user-type rouser user-name __nvOS_internal no-auth no-priv
snmp-vacm-create user-type rwuser user-name VINETro auth priv
snmp-vacm-create user-type rwuser user-name VINETrw auth priv
switch \* role-create name abcd scope local
"""

bgp_cmds = """
vrouter-interface-add vrouter-name hmplabpsq-we50500-vrouter nic eth7.4091 ip 104.255.61.65/31 ip2 2620:0:167f:b001::32/126 vlan 4091 l3-port 1 mtu 9216 
vrouter-modify vrouter-name hmplabpsq-we50500-vrouter bgp-as 65542
vrouter-modify vrouter-name hmplabpsq-we50600-vrouter bgp-as 65542
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.9/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.8/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.7/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.6/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.5/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.2/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.1/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.64/26
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::10/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::11/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::12/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::13/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::14/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::15/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::16/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::17/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::18/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b000::19/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b015::/64
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::10/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::11/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::12/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::13/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::14/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::15/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::16/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::17/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::18/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b010::19/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::38/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::3c/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::40/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::44/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::48/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::4c/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::50/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::54/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::58/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::5c/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::60/126
vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter network 2620:0:167f:b001::64/126
vrouter-bgp-add vrouter-name hmplabpsq-we50500-vrouter neighbor 104.255.61.64 remote-as 65020 next-hop-self soft-reconfig-inbound
vrouter-bgp-add vrouter-name hmplabpsq-we50500-vrouter neighbor 104.255.61.91 remote-as 65542
vrouter-bgp-add vrouter-name hmplabpsq-we50500-vrouter neighbor 2620:0:167f:b001::31 remote-as 65020 multi-protocol ipv6-unicast
vrouter-ospf-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.7/32 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.76/31 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.90/31 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.144/29 ospf-area 0
vrouter-ospf-add vrouter-name hmplabpsq-we50500-vrouter network 104.255.61.96/31 ospf-area 0
 
vrouter-interface-add vrouter-name hmplabpsq-we50600-vrouter nic eth2.4090 ip 104.255.61.67/31 ip2 2620:0:167f:b001::36/126 vlan 4090 l3-port 1 mtu 9216 
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.10/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.8/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.7/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.6/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.5/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.2/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 104.255.61.1/32
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::10/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::11/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::12/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::13/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::14/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::15/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::16/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::17/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::18/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b000::19/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b015::/64
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::10/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::11/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::12/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::13/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::14/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::15/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::16/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::17/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::18/128
vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter network 2620:0:167f:b010::19/128
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
vrouter-pim-config-modify vrouter-name hmplabpsq-we60100-vrouter query-interval 10 querier-timeout 30
vrouter-pim-config-modify vrouter-name hmplabpsq-we60200-vrouter query-interval 10 querier-timeout 30
vrouter-pim-config-modify vrouter-name hmplabpsq-we50100-vrouter query-interval 10 querier-timeout 30
vrouter-pim-config-modify vrouter-name hmplabpsq-we50200-vrouter query-interval 10 querier-timeout 30
vrouter-pim-config-modify vrouter-name hmplabpsq-we50300-vrouter query-interval 10 querier-timeout 30
vrouter-pim-config-modify vrouter-name hmplabpsq-we50400-vrouter query-interval 10 querier-timeout 30
vrouter-pim-config-modify vrouter-name hmplabpsq-we50500-vrouter query-interval 10 querier-timeout 30
vrouter-pim-config-modify vrouter-name hmplabpsq-we50600-vrouter query-interval 10 querier-timeout 30
"""

cpu_class_cmds = """
cpu-class-modify name ospf hog-protect enable
cpu-class-modify name bgp hog-protect enable
cpu-class-modify name lacp hog-protect enable
cpu-class-modify name vrrp hog-protect enable
cpu-class-modify name local-subnet hog-protect enable
cpu-class-modify name stp hog-protect enable
cpu-class-modify name bfd hog-protect enable
cpu-class-modify name pim hog-protect enable
switch \* port-cos-bw-modify cos 0 port 1-104 min-bw-guarantee 68
switch \* port-cos-bw-modify cos 4 port 1-104 min-bw-guarantee 8
switch \* port-cos-bw-modify cos 5 port 1-104 min-bw-guarantee 20
switch \* port-cos-bw-modify cos 6 port 1-104 min-bw-guarantee 4
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
    elif must_show or not show_only:
        if end == "nl":
            print(msg)
        else:
            print(msg, end='')
    else:
        pass
################

######### Running Commands ####################
_print("### Setting up Inband IP v4/v6 on vlan 490...", must_show=True)
_print("### =========================================", must_show=True)
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

_print("### Setting vrouter interfaces on vlan 244...", must_show=True)
_print("### =========================================", must_show=True)
for cmd in vlan244_intfs_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")

_print("### Setting up tunnels...", must_show=True)
_print("### =====================", must_show=True)
for cmd in tunnel_setup_cmds.split("\n"):
    cmd = cmd.strip()
    if not cmd:
        continue
    _print("Running cmd: %s" % cmd)
    run_cmd(cmd)
    sleep(g_inter_cmd_sleep)
_print("")

_print("### Setting up syslog...", must_show=True)
_print("### ====================", must_show=True)
for cmd in syslog_cmds.split("\n"):
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
