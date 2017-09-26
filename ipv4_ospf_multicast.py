from __future__ import print_function
import subprocess
import argparse
import time
import sys

##################
# Constants
##################
g_loopback_ip = "104.255.61."
g_cluster_vlan = 4040
ipv6_start = 15360
ipv6_end = 15480

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
    '-t', '--type',
    # help='IP Type. Defaults to \"ipv4\"',
    help=argparse.SUPPRESS,
    choices=["ipv4", "ipv6"],
    required=False,
    default="ipv4",
)
parser.add_argument(
    '-p', '--prefix',
    # help='IP Prefix. Defaults to \"2607:f4a0:3:0:250:56ff:feac:\" '
    #      'or \"192.168.100.\" based on type',
    help='IP Prefix. Defaults to \"104.255.61.\"',
    required=False
)
parser.add_argument(
    '-s', '--subnet',
    # help='IP Subnet. Defaults to \"64\", only valid for IPv6',
    choices=["64", "126"],
    help=argparse.SUPPRESS,
    required=False,
    default="64"
)
args = vars(parser.parse_args())
if not args['prefix']:
    if args['type'] == "ipv6":
        args['prefix'] = "2607:f4a0:3:0:250:56ff:feac:"
    else:
        args['prefix'] = "104.255.61."

g_spine_list = [i.strip() for i in args['spine'].split(',')]

################
# UTIL FUNCTIONS
################


def give_ipv6(start, end):
    if args['subnet'] == "64":
        for i in range(1, 300):
            yield "2001:%s::1,2001:%s::2" % (i, i)
    else:
        tag = args['prefix']
        for i in range(start, end, 4):
            yield "%s%.4x,%s%.4x" % (tag, i + 1, tag, i + 2)


def give_ipv4():
    tag = args['prefix']
    for i in range(64, 255, 2):
        yield "%s%s,%s%s" % (tag, i, tag, i + 1)


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
for sw in g_fab_nodes:
    g_rid_info[sw] = g_loopback_ip + str(i)
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
i = 1
for c_node in g_cluster_nodes:
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

# Create vRouters
for swname in g_fab_nodes:
    print("Creating vRouter %s-vrouter on %s..." % (swname, swname), end='')
    sys.stdout.flush()
    run_cmd("switch %s vrouter-create name %s-vrouter vnet %s-global "
            "router-type hardware router-id %s proto-multi pim-ssm "
            "ospf-redistribute connected" % (
                swname, swname, g_fab_name, g_rid_info[swname]))
    print("Done")
    sys.stdout.flush()
    time.sleep(20)

# Create L3 interfaces with IPv6 addresssing
if args['type'] == 'ipv4':
    ip_generator = give_ipv4()
    netmask = '31'
    mproto = "ipv4-unicast"
else:
    ip_generator = give_ipv6(ipv6_start, ipv6_end)
    netmask = args['subnet']
    mproto = "ipv6-unicast"
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
    time.sleep(10)
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
    time.sleep(10)
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
