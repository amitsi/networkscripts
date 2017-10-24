#!/usr/bin/python

""" PN Tunnel Vxlan Add """

from __future__ import print_function
import subprocess
import argparse
import time

##################
# ARGUMENT PARSING
##################
parser = argparse.ArgumentParser(description='Tunnel Vxlan Add')
parser.add_argument(
    '-c', '--cluster-pair',
    help='comma separated pair of cluster switches separated by semi-colon',
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
g_pairs = []
try:
    for pair in args['cluster_pair'].split(';'):
        p0,p1 = pair.split(',')
        g_pairs.append((p0.strip(),p1.strip()))
except:
    print("Incorrect format for cluster-pair, must contain pair of "
          "switches separated by comma and each pair separated by semi-colon")
    exit(0)

if len(g_pairs) < 1:
    print("Incorrect number of switches specified. There must be "
          "atleast 1 pair")
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

# Get list of routers
g_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,")
for vinfo in vrouter_info:
    if not vinfo:
        print("No vrouters found")
        exit(0)
    vr_name = vinfo
    g_vrouters.append(vr_name)

# Validate cluster pairs
for pair in g_pairs:
    for sw in pair:
        if sw not in g_fab_nodes:
            print("Incorrect switch name %s" % sw)
            exit(0)
        if sw+"-vrouter" not in g_vrouters:
            print("Vrouter %s-vrouter doesn't exist" % sw)
            exit(0)

##################VLAN VXLAN Creation################

for pair in g_pairs:
    print("Creating cluster-scoped VLAN %s with VXLAN %s on %s" % (
                g_vlan_id, g_vxlan_id, pair[0]))
    run_cmd("switch %s vlan-create id %s scope cluster vxlan %s" % (
                pair[0], g_vlan_id, g_vxlan_id))
print("")

tun_info = run_cmd("tunnel-show format name,vrouter-name,peer-vrouter-name "
        "parsable-delim , scope cluster")
for tuninfo in tun_info:
    if not tuninfo:
        print("No tunnels found")
        exit(0)
    tunname, vr1, vr2 = tuninfo.split(',')
    found1, found2 = False, False
    for pair in g_pairs: 
        if vr1 in pair:
            found1 = True
        if vr2 in pair:
            found2 = True
    if found1 and found2:
        print("Adding vxlan %s to tunnel %s" % (g_vxlan_id, tunname))
        run_cmd("tunnel-vxlan-add name %s vxlan %s" % (tunname, g_vxlan_id))

################################################
