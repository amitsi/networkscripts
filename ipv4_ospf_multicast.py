from __future__ import print_function
import subprocess
import argparse
import time
import sys

##################
# Constants
##################
loopback_ip = "99.99.99."
ipv6_start = 15360
ipv6_end = 15480
cluster_vlan = 4040

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
    help='IP Type. Defaults to \"ipv4\"',
    choices=["ipv4", "ipv6"],
    required=False,
    default="ipv4"
)
parser.add_argument(
    '-p', '--prefix',
    help='IP Prefix. Defaults to \"2607:f4a0:3:0:250:56ff:feac:\" or \"192.168.100.\" based on type',
    required=False
)
parser.add_argument(
    '-s', '--subnet',
    help='IP Subnet. Defaults to \"64\", only valid for IPv6',
    choices=["64","126"],
    required=False,
    default = "64"
)
args = vars(parser.parse_args())
if not args['prefix']:
    args['prefix']="2607:f4a0:3:0:250:56ff:feac:" if args['type'] == "ipv6" else "192.168.100."

spine_list = [i.strip() for i in args['spine'].split(',')]

################
# UTIL FUNCTIONS
################

def give_ipv6(start, end):
    if args['subnet'] == "64":
        for i in range(1,300):
            yield "2001:%s::1,2001:%s::2" % (i,i)
    else:
        tag = args['prefix']
        for i in range(start,end,4):
            yield "%s%.4x,%s%.4x" %(tag,i+1,tag,i+2)

def give_ipv4():
    tag = args['prefix']
    for i in range(2,255,2):
        yield "%s%s,%s%s" %(tag,i,tag,i+1)

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

# Get Router-ID info
rid_info = {}
fnodes = run_cmd("fabric-node-show format name parsable-delim ,")
i = 1
for sw in spine_list:
    if sw not in fnodes:
        print("Incorrect spine name %s" % sw)
        exit(0)
for sw in fnodes:
    rid_info[sw] = loopback_ip + str(i)
    i += 1

cluster_cmd = "cluster-show format cluster-node-1,cluster-node-2, parsable-delim ,"
cluster_nodes = []
for cl in run_cmd(cluster_cmd):
    if not cl:
        print("No clusters found")
        exit(0)
    cls1,cls2 = cl.split(',')
    cluster_nodes.append((cls1,cls2))

# Enable all ports to get better visibility of the topology
for sw in fnodes:
    if sw in spine_list:
        continue
    run_cmd("switch %s port-config-modify port all enable" %sw)
time.sleep(5)

# Get Connected Links (not part of cluster)
links = []
cluster_links = []
lldp_cmd = "lldp-show format switch,local-port,port-id,sys-name parsable-delim ,"
for conn in run_cmd(lldp_cmd):
    sw1,p1,p2,sw2 = conn.split(',')
    # Skip Clustered links
    if (sw1,sw2) in cluster_nodes or (sw2,sw1) in cluster_nodes:
        continue
    # Skip non fabric nodes
    if sw1 not in fnodes or sw2 not in fnodes:
        continue
    if (sw2,p2,p1,sw1) not in links:
        links.append((sw1,p1,p2,sw2))

# Create vRouters
sw_cmd = "fabric-node-show format name,fab-name parsable-delim ,"
sw_details = run_cmd(sw_cmd)
for swinfo in sw_details:
    swname, fabname = swinfo.split(',')
    print("Creating vRouter %s-vrouter on %s..." %(swname, swname), end='')
    sys.stdout.flush()
    run_cmd("switch %s vrouter-create name %s-vrouter vnet %s-global router-type "
            "hardware router-id %s proto-multi pim-ssm ospf-redistribute connected" % (
            swname,swname,fabname,rid_info[swname]))
    print("Done")
    sys.stdout.flush()
    time.sleep(20)

# Create L3 interfaces with IPv6 addresssing
if args['type'] == 'ipv4':
    ip_generator = give_ipv4()
    netmask = '31'
    mproto = "ipv4-unicast"
else:
    ip_generator = give_ipv6(ipv6_start,ipv6_end)
    netmask = args['subnet']
    mproto = "ipv6-unicast"
for link in links:
    sw1,p1,p2,sw2 = link
    ip1,ip2 = ip_generator.next().split(',')
    #####vRouter-Interface#####
    print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s/%s..." %(sw1,p1,ip1,netmask), end='')
    sys.stdout.flush()
    run_cmd("switch %s port-config-modify port %s disable" %(sw1, p1))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/%s mtu 9216" %(sw1,p1,ip1,netmask))
    run_cmd("switch %s port-config-modify port %s enable" %(sw1, p1))
    print("Done")
    sys.stdout.flush()
    time.sleep(2)
    #####OSPF#####
    print("Adding OSPF for vrouter=%s-vrouter ip=%s..." %(sw1,ip1), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s ospf-area 0" %(sw1,ip1,netmask))
    print("Done")
    sys.stdout.flush()
    time.sleep(10)
    ########################################
    #####vRouter-Interface#####
    print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s/%s..." %(sw2,p2,ip2,netmask), end='')
    sys.stdout.flush()
    run_cmd("switch %s port-config-modify port %s disable" %(sw2, p2))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/%s mtu 9216" %(sw2,p2,ip2,netmask))
    run_cmd("switch %s port-config-modify port %s enable" %(sw2, p2))
    print("Done")
    sys.stdout.flush()
    time.sleep(2)
    #####OSPF#####
    print("Adding OSPF for vrouter=%s-vrouter ip=%s..." %(sw2,ip2), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s ospf-area 0" %(sw2,ip2,netmask))
    print("Done")
    sys.stdout.flush()
    time.sleep(10)

for sws in cluster_nodes:
    sw1,sw2 = sws
    ####Creation cluster VLANs####
    print("Creating VLAN 4040 cluster scope on switches: %s & %s..." %sws, end='')
    sys.stdout.flush()
    run_cmd("switch %s vlan-create id %s scope cluster" % (sw1,cluster_vlan))
    print("Done")
    sys.stdout.flush()
    time.sleep(1)
    ########################################
    ip1,ip2 = ip_generator.next().split(',')
    ########################################
    #####vRouter-Interface#####
    print("Adding vRouter interface to vrouter=%s-vrouter vlan=%s ip=%s/%s..." %(sw1,cluster_vlan,ip1,netmask), end='')
    sys.stdout.flush()
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter vlan %s ip %s/%s mtu 9216 pim-cluster" %(sw1,cluster_vlan,ip1,netmask))
    print("Done")
    sys.stdout.flush()
    time.sleep(2)
    #####OSPF#####
    print("Adding OSPF for vrouter=%s-vrouter ip=%s..." %(sw1,ip1), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s ospf-area 0" %(sw1,ip1,netmask))
    print("Done")
    sys.stdout.flush()
    time.sleep(5)
    ########################################
    #####vRouter-Interface#####
    print("Adding vRouter interface to vrouter=%s-vrouter vlan=%s ip=%s/%s..." %(sw2,cluster_vlan,ip2,netmask), end='')
    sys.stdout.flush()
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter vlan %s ip %s/%s mtu 9216 pim-cluster" %(sw2,cluster_vlan,ip2,netmask))
    print("Done")
    sys.stdout.flush()
    time.sleep(2)
    #####OSPF#####
    print("Adding OSPF for vrouter=%s-vrouter ip=%s..." %(sw2,ip2), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s ospf-area 0" %(sw2,ip2,netmask))
    print("Done")
    sys.stdout.flush()
    time.sleep(5)
