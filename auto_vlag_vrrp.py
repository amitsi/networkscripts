from __future__ import print_function
from binascii import hexlify
import subprocess
import argparse
import errno
import struct
import socket
import time
import sys
import io
import re
import ConfigParser

#===============================================================================
# Sample Config File:
#===============================================================================
"""
[global]
vrouter-count = 2
vrrp-id = 15
vrrp-master-priority = 99

[spine1]
name = ara00
peer-name = ara01
vrouter-prefix = ara00-spine1

[spine2]
name = ara01
peer-name = ara00
vrouter-prefix = ara01-spine2

[vrrp]
vr1 = 101,10.100.101.1/24,ara00
vr2 = 102,10.100.102.1/24,ara01
"""

#===============================================================================
# Script Notes:
#===============================================================================
"""
1. Create cluster on spines/leafs
2. Setup VLAGS spines/leafs
3. Create vNETs/vRouters on spines
4. Setup VRRP on spines
"""

#===============================================================================
# ARGUMENT PARSING
#===============================================================================

parser = argparse.ArgumentParser(description='Steelcase vLAG-VRRP setup script')
parser.add_argument(
    '-c', '--config',
    help='config file',
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
g_config_file = args["config"]

with open(g_config_file, 'r') as conffile:
    sample_config = conffile.read()
config = ConfigParser.RawConfigParser(allow_no_value=True)
config.readfp(io.BytesIO(sample_config))

g_spines = {}
g_vrrps = {}
g_vr_count = 0
g_vrrp_id = 15
g_vrrp_pri = 110
for section in config.sections():
    if section.startswith("global"):
        g_vr_count = int(config.get(section, "vrouter-count"))
        g_vrrp_id = int(config.get(section, "vrrp-id"))
        g_vrrp_pri = int(config.get(section, "vrrp-master-priority"))
    if section.startswith("spine"):
        name = config.get(section, "name")
        peer_name = config.get(section, "peer-name")
        vr_prefix = config.get(section, "vrouter-prefix")
        g_spines[name] = (peer_name, vr_prefix)
    if section.startswith("vrrp"):
        for options in config.options(section):
            g_vrrps[options] = config.get(section, options).split(',')

#===============================================================================
# UTIL FUNCTIONS
#===============================================================================

def validate_ipv4_cidr(ip):
    CIDR_RE = re.compile(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.)"
                         "{3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])"
                         "(\/([0-9]|[1-2][0-9]|3[0-2]))$")
    if CIDR_RE.match(ip):
        return True
    return False

def give_ipv4_ip(ip_cidr):
    (ip, cidr) = ip_cidr.split('/')
    host_bits = 32 - int(cidr)
    i = struct.unpack('>I', socket.inet_aton(ip))[0] # note the endianness
    start = i
    end = i | ((1 << host_bits) - 1)
    for i in range(start, end):
        yield socket.inet_ntoa(struct.pack('>I', i)) + '/' + cidr

def run_cmd(cmd, ignore_err=False):
    ignore_err_list = [errno.EEXIST]
    m_cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    if show_only and "-show" not in cmd:
        print("### " + cmd)
        return
    try:
        proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        if not ignore_err and \
           proc.returncode and \
           proc.returncode not in ignore_err_list:
            print("Failed running cmd %s" % m_cmd)
            print("Retrying in 5 seconds....")
            sys.stdout.flush()
            time.sleep(5)
            proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
            output = proc.communicate()[0]
            if proc.returncode:
                print("Failed again... Giving up !")
                exit(1)
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

def get_vlag_port(sw1, sw2, port):
    port_info = run_cmd("switch %s port-show hostname %s port %s "
                        "format status parsable-delim ," % (sw1, sw2, port))
    for pinfo in port_info:
        if not pinfo:
            print("No port found for host %s" % sw2)
            exit(0)
        if "trunk" not in pinfo:
            return port
        trunk_info = run_cmd("switch %s trunk-show ports %s format name"
                             " parsable-delim ," % (sw1, port))
        for tinfo in trunk_info:
            if not tinfo:
                print("No trunk found for port %s" % port)
                exit(0)
            return tinfo
    print("No port found to %s from %s" % (sw2, sw1))
    exit(0)

#===============================================================================
# Validation
#===============================================================================

# Get list of fabric nodes
g_fab_nodes = []
g_fab_name = ""
fab_info = run_cmd("fabric-node-show format name,fab-name parsable-delim ,")
for finfo in fab_info:
    if not finfo:
        print("No fabric output")
        exit(0)
    sw_name, fab_name = finfo.split(',')
    g_fab_nodes.append(sw_name)
    g_fab_name = fab_name

# Validate spine list
for sw in g_spines:
    if sw not in g_fab_nodes:
        print("Incorrect spine name %s" % sw)
        exit(0)

# Get all the connected links - sw1,p1,p2,sw2
g_main_links = []
lldp_cmd = "lldp-show format switch,local-port,port-id,sys-name parsable-delim ,"
for conn in run_cmd(lldp_cmd):
    if not conn:
        _print("No LLDP output")
        exit(0)
    g_main_links.append(conn.split(','))

g_leaf_cluster = set()
g_spine_leaf = {}
for conn in g_main_links:
    sw1, p1, p2, sw2 = conn
    # Skip non fabric nodes
    if sw1 not in g_fab_nodes or sw2 not in g_fab_nodes:
        continue
    # Get cluster node list
    if sw1 in g_spines and sw2 in g_spines:
        pass
    elif sw1 in g_spines:
        if not g_spine_leaf.get(sw1, None):
            g_spine_leaf[sw1] = [(sw2,p1)]
        else:
            if (sw2,p1) not in g_spine_leaf[sw1]:
                g_spine_leaf[sw1].append((sw2,p1))
                if len(g_spine_leaf[sw1]) > 2:
                    print("Ports from spine %s has more than two leafs "
                          "connected to it" % sw1)
                    sys.exit(0)
        if not g_spine_leaf.get(sw2, None):
            g_spine_leaf[sw2] = [(sw1,p2)]
        else:
            if (sw1,p2) not in g_spine_leaf[sw2]:
                g_spine_leaf[sw2].append((sw1,p2))
                if len(g_spine_leaf[sw2]) > 2:
                    print("Ports from leaf %s has more than two spines "
                          "connected to it" % sw2)
                    sys.exit(0)
    elif sw2 in g_spines:
        if not g_spine_leaf.get(sw2, None):
            g_spine_leaf[sw2] = [(sw1,p2)]
        else:
            if (sw1,p2) not in g_spine_leaf[sw2]:
                g_spine_leaf[sw2].append((sw1,p2))
                if len(g_spine_leaf[sw2]) > 2:
                    print("Ports from spine %s has more than two leafs "
                          "connected to it" % sw2)
                    sys.exit(0)
            if not g_spine_leaf.get(sw1, None):
                g_spine_leaf[sw1] = [(sw2,p1)]
            else:
                if (sw2,p1) not in g_spine_leaf[sw1]:
                    g_spine_leaf[sw1].append((sw2,p1))
                    if len(g_spine_leaf[sw1]) > 2:
                        print("Ports from leaf %s has more than two spines "
                              "connected to it" % sw1)
                        sys.exit(0)
    else:
        if (sw1, sw2) not in g_leaf_cluster \
            and (sw2, sw1) not in g_leaf_cluster:
            g_leaf_cluster.add((sw1, sw2))

#===============================================================================
# Cluster Creation
#===============================================================================

existing_clusters = []
cluster_info = run_cmd("cluster-show format cluster-node-1,cluster-node-2 "
                       "parsable-delim ,")
for cinfo in cluster_info:
    if not cinfo:
        break
    nodes = cinfo.split(",")
    existing_clusters.append(tuple(nodes))

_print("")
_print("### Configure Spine Clusters", must_show=True)
_print("### ========================", must_show=True)

i = 1
g_spine_cluster = []
for spine_sw in g_spines:
    c_node = (spine_sw, g_spines[spine_sw][0])
    if c_node in existing_clusters:
        continue
    sw1, sw2 = c_node
    if (sw1, sw2) in g_spine_cluster or (sw2, sw1) in g_spine_cluster:
        continue
    g_spine_cluster.append(c_node)
    _print("Creating cluster: spine-cluster-%d between %s & %s" % (i, sw1, sw2))
    run_cmd("cluster-create name spine-cluster-%d cluster-node-1 %s "
            "cluster-node-2 %s" % (i, sw1, sw2))
    i += 1

_print("")
_print("### Configure Leaf Clusters", must_show=True)
_print("### =======================", must_show=True)
if len(g_leaf_cluster) == 0:
    _print("No leaf cluster nodes found", must_show=True)
else:
    i = 1
    for c_node in g_leaf_cluster:
        if c_node in existing_clusters:
            continue
        sw1, sw2 = c_node
        _print("Creating cluster: leaf-cluster-%d between %s & %s" % (i, sw1, sw2))
        run_cmd("cluster-create name leaf-cluster-%d cluster-node-1 %s "
                "cluster-node-2 %s" % (i, sw1, sw2))
        i += 1

#===============================================================================
# vLAG Creation
#===============================================================================

existing_vlags = []
vlag_info = run_cmd("vlag-show format name parsable-delim ,")
for vinfo in vlag_info:
    if not vinfo:
        break
    existing_vlags.append(vinfo)

_print("")
_print("### Configure Spine-<->-Leaf vLAG", must_show=True)
_print("### =============================", must_show=True)

for sw in g_spine_leaf:
    p_sw1, p_port1 = g_spine_leaf[sw][0]
    p_sw2, p_port2 = g_spine_leaf[sw][1]
    exists = False
    for sp1,sp2 in g_spine_cluster:
        if sw == sp2:
            exists = True
            break
    if exists: continue
    for l1,l2 in g_leaf_cluster:
        if sw == l2:
            exists = True
            break
    if exists: continue
    if (p_sw1 > p_sw2):
        v_name = "to-%s-%s" % (p_sw1, p_sw2)
    else:
        v_name = "to-%s-%s" % (p_sw2, p_sw1)
    if v_name in existing_vlags:
        continue
    v_port_1 = get_vlag_port(sw, p_sw1, p_port1)
    v_port_2 = get_vlag_port(sw, p_sw2, p_port2)
    _print("Creating vlag on %s: %s with port %s peer-port %s" % (
        sw, v_name, v_port_1, v_port_2))
    run_cmd("switch %s vlag-create name %s port %s peer-port %s" % (
        sw, v_name, v_port_1, v_port_2))

#===============================================================================
# vRouter Creation
#===============================================================================

existing_vnets = []
vnet_info = run_cmd("vnet-show format name parsable-delim ,")
for vinfo in vnet_info:
    if not vinfo:
        break
    vn_name = vinfo
    existing_vnets.append(vn_name)

existing_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,")
for vinfo in vrouter_info:
    if not vinfo:
        break
    vr_name = vinfo
    existing_vrouters.append(vr_name)

_print("")
_print("### Configure Spine vRouters", must_show=True)
_print("### ========================", must_show=True)

for swname in g_spines:
    for vr_index in range(1, g_vr_count+1):
        vnname = g_spines[swname][1] + "-vn" + str(vr_index)
        if vnname in existing_vnets:
            continue
        _print("Creating vNET %s on %s..." % (vnname, swname), end='')
        sys.stdout.flush()
        run_cmd("switch %s vnet-create name %s scope fabric" % (
                    swname, vnname))
        sleep(2)
        _print("Done")
        sys.stdout.flush()
        vrname = g_spines[swname][1] + "-vr" + str(vr_index)
        if vrname in existing_vrouters:
            continue
        _print("Creating vRouter %s on %s..." % (vrname, swname), end='')
        sys.stdout.flush()
        run_cmd("switch %s vrouter-create name %s vnet %s "
                "router-type hardware" % (swname, vrname, vnname))
        sleep(2)
        _print("Done")
        sys.stdout.flush()

#===============================================================================
# Setup VRRP for Spines Nodes
#===============================================================================

for vr_index in g_vrrps:
    _print("")
    _print("### Configure VRRP for all spine vrouter %s" % vr_index,
           must_show=True)
    _print("### ========================================", must_show=True)
    vrrp_vlan = int(g_vrrps[vr_index][0])
    vrrp_network = g_vrrps[vr_index][1]
    active_switch = g_vrrps[vr_index][2]
    if not validate_ipv4_cidr(vrrp_network):
        print("Incorrect IP address format: %s" % vrrp_network)
        exit(0)
    ip_gen = give_ipv4_ip(vrrp_network)
    primary_ips = []
    try:
        vip = ip_gen.next()
        for i in range(len(g_spines)):
            primary_ips.append(ip_gen.next())
    except StopIteration:
        print("Unable to generate more IPs from this range: %s" % vrrp_network)
        exit(0)

    vlan_created = False
    vrrp_id_set = False
    ip_index = 0
    pri_offset = 1
    for swname in g_spines:
        vrname = g_spines[swname][1] + "-" + vr_index
        prim_ip = primary_ips[ip_index]
        ip_index += 1
        if not vlan_created:
            print("Creating vrrp vlan fabric scoped: %d on %s" % (vrrp_vlan, swname))
            run_cmd("switch %s vlan-create id %d scope cluster" % (swname, vrrp_vlan))
            vlan_created = True
            print("")
        if not vrrp_id_set:
            print("Set vrrp-id %d for %s" % (g_vrrp_id, vrname))
            run_cmd("vrouter-modify name %s hw-vrrp-id %d" % (vrname, g_vrrp_id))
            print("")

        print("Creating primary interface on sw: %s with ip: %s, vlan-id: "
              "%s" % (swname, prim_ip, vrrp_vlan))
        run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s if "
                "data" % (vrname, prim_ip, vrrp_vlan))
        sleep(1)
        print("")

        intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s ip %s "
                        "vlan %s format nic parsable-delim ," % (
                            swname, vrname, prim_ip, vrrp_vlan))
        for intf in intf_info:
            if not intf:
                if show_only:
                    pintf_index = "<nic>"
                    break
                else:
                    print("No router interface exist")
                    exit(0)
            pintf_index = intf.split(',')[1]
            break

        if swname == active_switch:
            vrrp_pri = g_vrrp_pri
        else:
            vrrp_pri = g_vrrp_pri + pri_offset
            pri_offset += 1

        print("Setting vrrp-vip interface on sw: %s with vip: %s, vlan-id: %s, "
              "vrrp-id: %s, vrrp-priority: %s" % (swname, vip, vrrp_vlan,
                                                  g_vrrp_id, vrrp_pri))
        run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s "
                "if data vrrp-id %s vrrp-primary %s vrrp-priority %s" % (
                    vrname, vip, vrrp_vlan, g_vrrp_id, pintf_index, vrrp_pri))
        sleep(1)
        print("")

    vrrp_id_set = True
