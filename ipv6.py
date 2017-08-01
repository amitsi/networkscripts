from __future__ import print_function
import subprocess
import argparse
import time
import sys

##################
# Constants
##################
loopback_ip = "99.99.99."
asnum = 65000
ipv6_start = 15360
ipv6_end = 15380

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Setup IPv4/IPv6 L3 BGP Network')
parser.add_argument(
    '-t', '--type',
    help='IP Type. Defaults to \"ipv6\"',
    choices=["ipv4", "ipv6"],
    required=False,
    default="ipv6"
)
parser.add_argument(
    '-p', '--prefix',
    help='IP Prefix. Defaults to \"2607:f4a0:3:0:250:56ff:feac:\" or \"192.168.100.\" based on type',
    required=False
)
args = vars(parser.parse_args())
if not args['prefix']:
    args['prefix']="2607:f4a0:3:0:250:56ff:feac:" if args['type'] == "ipv6" else "192.168.100."

################
# UTIL FUNCTIONS
################

def give_ipv6(start, end):
    tag = args['prefix']
    for i in range(start,end,4):
        yield "%s%.4x,%s%.4x" %(tag,i+1,tag,i+2)

def give_ipv4():
    tag = args['prefix']
    for i in range(1,255):
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

# Get AS number & Router-ID info
as_info = {}
cluster_cmd = "cluster-show format cluster-node-1,cluster-node-2, parsable-delim ,"
cluster_nodes = []
for cl in run_cmd(cluster_cmd):
    cls1,cls2 = cl.split(',')
    cluster_nodes.append((cls1,cls2))
    as_info[cls1] = asnum
    as_info[cls2] = asnum
    asnum += 1
rid_info = {}
fnodes = run_cmd("fabric-node-show format name parsable-delim ,")
i = 1
for sw in fnodes:
    rid_info[sw] = loopback_ip + str(i)
    i += 1
    if not as_info.get(sw, None):
        as_info[sw] = asnum
        asnum += 1

# Enable all ports to get better visibility of the topology
run_cmd("switch \* port-config-modify port all enable")
run_cmd("switch \* stp-modify disable")

# Get Connected Links (not part of cluster)
links = []
lldp_cmd = "lldp-show format switch,local-port,port-id,sys-name parsable-delim ,"
for conn in run_cmd(lldp_cmd):
    sw1,p1,p2,sw2 = conn.split(',')
    # Skip Clustered links
    if (sw1,sw2) in cluster_nodes or (sw2,sw1) in cluster_nodes:
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
            "hardware bgp-as %s router-id %s" % (
            swname,swname,fabname,as_info[swname],rid_info[swname]))
    print("Done")
    sys.stdout.flush()
    time.sleep(2)

# Create L3 interfaces with IPv6 addresssing
if args['prefix'] == 'ipv4':
    ip_generator = give_ipv4()
    netmask = '31'
    mproto = "ipv4-unicast"
else:
    ip_generator = give_ipv6(ipv6_start,ipv6_end)
    netmask = '126'
    mproto = "ipv6-unicast"
for link in links:
    sw1,p1,p2,sw2 = link
    ip1,ip2 = ip_generator.next().split(',')
    #####vRouter-Interface#####
    print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s/%s..." %(sw1,p1,ip1,netmask), end='')
    sys.stdout.flush()
    run_cmd("switch %s port-config-modify port %s disable" %(sw1, p1))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/%s" %(sw1,p1,ip1,netmask))
    run_cmd("switch %s port-config-modify port %s enable" %(sw1, p1))
    print("Done")
    sys.stdout.flush()
    #####BGP-Neighbor#####
    print("Adding BGP neighbor for vrouter=%s-vrouter ip=%s remote-as=%s..." %(sw1,ip2,as_info[sw2]), end='')
    sys.stdout.flush()
    run_cmd("vrouter-bgp-add vrouter-name %s-vrouter neighbor %s remote-as %s "
            "multi-protocol %s" %(sw1,ip2,as_info[sw2],mproto))
    print("Done")
    sys.stdout.flush()
    ########################################
    #####vRouter-Interface#####
    print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s/%s..." %(sw2,p2,ip2,netmask), end='')
    sys.stdout.flush()
    run_cmd("switch %s port-config-modify port %s disable" %(sw2, p2))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/%s" %(sw2,p2,ip2,netmask))
    run_cmd("switch %s port-config-modify port %s enable" %(sw2, p2))
    print("Done")
    sys.stdout.flush()
    #####BGP-Neighbor#####
    print("Adding BGP neighbor for vrouter=%s-vrouter ip=%s remote-as=%s..." %(sw2,ip1,as_info[sw1]), end='')
    sys.stdout.flush()
    run_cmd("vrouter-bgp-add vrouter-name %s-vrouter neighbor %s remote-as %s "
            "multi-protocol %s" %(sw2,ip1,as_info[sw1],mproto))
    print("Done")
    sys.stdout.flush()
