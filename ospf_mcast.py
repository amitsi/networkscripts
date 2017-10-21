from __future__ import print_function
import subprocess
import argparse
import time
import sys

##################
# Constants
##################
g_loopback_ip = "104.255.61.1"
g_ipv4_start = "104.255.61.64"
g_ipv6_start = "2620:0000:167F:b001::30"
g_cluster_vlan = 4040
g_netmask_v4 = 31
g_netmask_v6 = 127

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Setup IPv4 L3 OSPF Network')
parser.add_argument(
    '-S', '--spine',
    help='list of spines separated by comma',
    required=True
)
parser.add_argument(
    '--ipv4',
    action='store_true'
)
parser.add_argument(
    '--ipv6',
    action='store_true'
)
args = vars(parser.parse_args())

set_ipv4 = False
set_ipv6 = False
if args['ipv4']:
    set_ipv4 = True
if args['ipv6']:
    set_ipv6 = True

g_spine_list = [i.strip() for i in args['spine'].split(',')]

################
# UTIL FUNCTIONS
################

def is_hex(s):
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


def ip_key(entry):
    ip = entry[-1]
    return int(ip.split('.')[-1])


def give_ipv6():
    ip_split = g_ipv6_start.split(':')
    ipprefix = ':'.join(ip_split[:-1])
    lastoct = ip_split[-1]
    if not is_hex(lastoct):
        print("Unsupported IPv6 value, must have last octet as hex value")
        exit(0)
    istart = int(lastoct, 16)
    iend = int('ffff', 16)
    for i in range(istart, iend):
        yield "%s:%.4x" % (ipprefix, i)


def give_ipv4():
    ip_split = g_ipv4_start.split('.')
    ipprefix = '.'.join(ip_split[:-1])
    lastoct = int(ip_split[-1])
    for i in range(lastoct, 255, 2):
        yield "%s.%s,%s.%s" % (ipprefix, i, ipprefix, i + 1)


def give_loopback_v4():
    ip_split = g_loopback_ip.split('.')
    ipprefix = '.'.join(ip_split[:-1])
    lastoct = int(ip_split[-1])
    for i in range(lastoct, 255):
        yield "%s.%s" % (ipprefix, i)


def run_cmd(cmd):
    cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % cmd)
        exit(0)

################

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
for sw in g_spine_list:
    if sw not in g_fab_nodes:
        print("Incorrect spine name %s" % sw)
        exit(0)

# Get Router-ID info
g_rid_info = {}
i = 1
loopback_gen = give_loopback_v4()
for sw in g_fab_nodes:
    g_rid_info[sw] = loopback_gen.next()
    i += 1

# Get all the connected links - sw1,p1,p2,sw2
g_main_links = []
lldp_cmd = "lldp-show format switch,local-port,port-id,sys-name parsable-delim ,"
for conn in run_cmd(lldp_cmd):
    if not conn:
        print("No LLDP output")
        exit(0)
    g_main_links.append(conn.split(','))

g_cluster_nodes = set()
for conn in g_main_links:
    sw1, p1, p2, sw2 = conn
    # Skip non fabric nodes
    if sw1 not in g_fab_nodes or sw2 not in g_fab_nodes:
        continue
    # Disable spine ports
    if sw1 in g_spine_list and sw2 in g_spine_list:
        print("Disabling spine link on %s. Port: %s" % (sw1, p1))
        run_cmd("switch %s port-config-modify port %s disable" % (sw1, p1))
    # Get cluster node list
    if sw1 not in g_spine_list and sw2 not in g_spine_list:
        if (sw1, sw2) not in g_cluster_nodes \
            and (sw2, sw1) not in g_cluster_nodes:
            g_cluster_nodes.add((sw1, sw2))

# Create Clusters
if len(g_cluster_nodes) == 0:
    print("No cluster nodes found")
    exit(0)

existing_clusters = []
cluster_info = run_cmd("cluster-show format cluster-node-1,cluster-node-2 "
                       "parsable-delim ,")
for cinfo in cluster_info:
    if not cinfo:
        break
    existing_clusters.append(cinfo)

i = 1
for c_node in g_cluster_nodes:
    if c_node in existing_clusters:
        continue
    sw1, sw2 = c_node
    print("Creating cluster: cluster-leaf%d between %s & %s" % (i, sw1, sw2))
    run_cmd("cluster-create name cluster-leaf%d cluster-node-1 %s "
            "cluster-node-2 %s" % (i, sw1, sw2))
    i += 1

# Get Connected Links (not part of cluster)
g_l3_links = []
for conn in g_main_links:
    sw1, p1, p2, sw2 = conn
    # Skip Clustered links
    if (sw1, sw2) in g_cluster_nodes or (sw2, sw1) in g_cluster_nodes:
        continue
    # Skip non fabric nodes
    if sw1 not in g_fab_nodes or sw2 not in g_fab_nodes:
        continue
    # Skip spine links
    if sw1 in g_spine_list and sw2 in g_spine_list:
        continue
    if (sw2, p2, p1, sw1) not in g_l3_links:
        g_l3_links.append((sw1, p1, p2, sw2))

existing_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,")
for vinfo in vrouter_info:
    if not vinfo:
        break
    vr_name = vinfo
    existing_vrouters.append(vr_name)
# Create vRouters
for swname in g_fab_nodes:
    vrname = "%s-vrouter" % swname
    if vrname in existing_vrouters:
        continue
    print("Creating vRouter %s on %s..." % (vrname, swname), end='')
    sys.stdout.flush()
    run_cmd("switch %s vrouter-create name %s vnet %s-global "
            "router-type hardware router-id %s proto-multi pim-ssm "
            "ospf-redistribute connected" % (
                swname, vrname, g_fab_name, g_rid_info[swname]))
    run_cmd("switch %s vrouter-loopback-interface-add vrouter-name %s "
            "ip %s" % (swname, vrname, g_rid_info[swname]))
    print("Done")
    sys.stdout.flush()
    time.sleep(3)

# Create L3 interfaces with IPv4 addresssing
if set_ipv4:
    ip_generator = give_ipv4()
    netmask = g_netmask_v4

    print("")
    for link in g_l3_links:
        sw1, p1, p2, sw2 = link
        # Give lower ip to spine node
        if sw2 in g_spine_list:
            sw2, p2, p1, sw1 = sw1, p1, p2, sw2
        ip1, ip2 = ip_generator.next().split(',')
        #####vRouter-Interface#####
        print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s/%s..." %
              (sw1, p1, ip1, netmask), end='')
        sys.stdout.flush()
        run_cmd("switch %s port-config-modify port %s disable" % (sw1, p1))
        run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip "
                "%s/%s " % (sw1, p1, ip1, netmask))
        run_cmd("switch %s port-config-modify port %s enable" % (sw1, p1))
        print("Done")
        sys.stdout.flush()
        time.sleep(2)
        #####OSPF#####
        print("Adding OSPF for vrouter=%s-vrouter ip=%s..." % (sw1, ip1), end='')
        sys.stdout.flush()
        run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
                "ospf-area 0" % (sw1, ip1, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(5)
        ########################################
        #####vRouter-Interface#####
        print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s/%s..." %
              (sw2, p2, ip2, netmask), end='')
        sys.stdout.flush()
        run_cmd("switch %s port-config-modify port %s disable" % (sw2, p2))
        run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip "
                "%s/%s " % (sw2, p2, ip2, netmask))
        run_cmd("switch %s port-config-modify port %s enable" % (sw2, p2))
        print("Done")
        sys.stdout.flush()
        time.sleep(2)
        #####OSPF#####
        print("Adding OSPF for vrouter=%s-vrouter ip=%s..." % (sw2, ip2), end='')
        sys.stdout.flush()
        run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
                "ospf-area 0" % (sw2, ip2, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(5)

    print("")
    for sws in g_cluster_nodes:
        sw1, sw2 = sws
        # Give lower ip to spine node
        if sw2 in g_spine_list:
            sw1, sw2 = sw2, sw1
        ####Creation cluster VLANs####
        print("Creating VLAN 4040 cluster scope on switches: %s & %s..." % sws,
              end='')
        sys.stdout.flush()
        run_cmd("switch %s vlan-create id %s scope cluster" %
                (sw1, g_cluster_vlan))
        print("Done")
        sys.stdout.flush()
        time.sleep(1)
        ########################################
        ip1, ip2 = ip_generator.next().split(',')
        ########################################
        #####vRouter-Interface#####
        print("Adding vRouter interface to vrouter=%s-vrouter vlan=%s ip=%s/%s..." %
              (sw1, g_cluster_vlan, ip1, netmask), end='')
        sys.stdout.flush()
        run_cmd("vrouter-interface-add vrouter-name %s-vrouter vlan %s ip %s/%s "
                "pim-cluster" % (sw1, g_cluster_vlan, ip1, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(2)
        #####OSPF#####
        print("Adding OSPF for vrouter=%s-vrouter ip=%s..." % (sw1, ip1), end='')
        sys.stdout.flush()
        run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
                "ospf-area 0" % (sw1, ip1, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(5)
        ########################################
        #####vRouter-Interface#####
        print("Adding vRouter interface to vrouter=%s-vrouter vlan=%s ip=%s/%s..." %
              (sw2, g_cluster_vlan, ip2, netmask), end='')
        sys.stdout.flush()
        run_cmd("vrouter-interface-add vrouter-name %s-vrouter vlan %s ip %s/%s "
                "pim-cluster" % (sw2, g_cluster_vlan, ip2, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(2)
        #####OSPF#####
        print("Adding OSPF for vrouter=%s-vrouter ip=%s..." % (sw2, ip2), end='')
        sys.stdout.flush()
        run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
                "ospf-area 0" % (sw2, ip2, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(5)
    print("")

# Create L3 interfaces with IPv6 addresssing
if set_ipv6:
    v4_interfaces = []
    int_info = run_cmd("vrouter-interface-show format nic,l3-port,ip parsable-delim ,")
    for v4_int in int_info:
        if not v4_int:
            print("No IPv4 interfaces configured")
            exit(0)
        entry = v4_int.split(',')
        if entry[-2]:
            v4_interfaces.append(v4_int.split(','))
            v4_interfaces = sorted(v4_interfaces, key=ip_key)

    if not len(v4_interfaces):
        print("No IPv4 interfaces configured")
        exit(0)
    ip_generator = give_ipv6()
    netmask = g_netmask_v6

    for interface in v4_interfaces:
        ipaddr = ip_generator.next()
        vr_name, nic, l3_port, v4_ip = interface
        #####vRouter-Interface#####
        print("Adding vRouter IPv6 interface to vrouter=%s nic=%s ip=%s/%s..." %
              (vr_name, nic, ipaddr, netmask), end='')
        run_cmd("vrouter-interface-ip-add vrouter-name %s nic %s ip %s/%s" % (vr_name, nic, ipaddr, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(2)
        #####OSPF#####
        print("Adding OSPF for IPv6 network on vrouter=%s nic=%s..." % (vr_name, nic), end='')
        sys.stdout.flush()
        run_cmd("vrouter-ospf6-add vrouter-name %s nic %s ospf6-area 0.0.0.0" % (vr_name, nic))
        print("Done")
        sys.stdout.flush()
        time.sleep(5)

    v4_interfaces = []
    int_info = run_cmd("vrouter-interface-show vlan 4040 format nic,ip parsable-delim ,")
    for v4_int in int_info:
        if not v4_int:
            print("No IPv4 iOSPF links configured")
            exit(0)
        entry = v4_int.split(',')
        v4_interfaces.append(v4_int.split(','))
        v4_interfaces = sorted(v4_interfaces, key=ip_key)

    if not len(v4_interfaces):
        print("No IPv4 iOSPF links configured")
        exit(0)

    print("")
    print("Adding IPv6 interfaces for iOSPF links:")
    for interface in v4_interfaces:
        ipaddr = ip_generator.next()
        vr_name, nic, v4_ip = interface
        #####vRouter-Interface#####
        print("Adding vRouter IPv6 interface to vrouter=%s nic=%s ip=%s/%s..." %
              (vr_name, nic, ipaddr, netmask), end='')
        run_cmd("vrouter-interface-ip-add vrouter-name %s nic %s ip %s/%s" % (vr_name, nic, ipaddr, netmask))
        print("Done")
        sys.stdout.flush()
        time.sleep(2)
        #####OSPF#####
        print("Adding OSPF for IPv6 network on vrouter=%s nic=%s..." % (vr_name, nic), end='')
        sys.stdout.flush()
        run_cmd("vrouter-ospf6-add vrouter-name %s nic %s ospf6-area 0.0.0.0" % (vr_name, nic))
        print("Done")
        sys.stdout.flush()
        time.sleep(5)
