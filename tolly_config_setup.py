from __future__ import print_function
import subprocess
import argparse
import errno
import time
import sys

####################
# Dynamic Constants
####################
g_loopback_ipv4 = "104.255.61.1"
g_loopback_ipv6 = "2620:0000:167F:b000::10"
g_ipv4_start = "104.255.61.68"
g_ipv6_start = "2620:0000:167F:b001::40"
g_cluster_vlan = 4040
g_jumbo_mtu = True
g_loopback_skip_octv4 = [3, 4]
g_loopback_skip_octv6 = [0x12, 0x13]
g_vrrp_id = 15
g_prim_vrrp_pri = 110
g_sec_vrrp_pri = 109

####################
# Static Constants
####################
# Supported v4 subnet: 31
g_netmask_v4 = 31
# Supported v6 subnets: 126 | 127
g_netmask_v6 = 126

ignore_err_list = [errno.EEXIST]

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Setup IPv4/v6 OSPF Mcast Network')
parser.add_argument(
    '-S', '--spine',
    help='list of spines separated by comma',
    required=True
)
parser.add_argument(
    '--show-only',
    help='will show commands it will run',
    action='store_true',
    required=False
)
parser.add_argument(
    '--debug',
    help='enable debug xact',
    action='store_true',
    required=False
)
args = vars(parser.parse_args())

show_only = args["show_only"]
debug = args["debug"]

g_spine_list = [i.strip() for i in args['spine'].split(',')]
if g_jumbo_mtu:
    g_mtu = 9216
else:
    g_mtu = 1500

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
    if g_netmask_v6 == 127:
        for i in range(istart, iend):
            yield "%s:%.4x" % (ipprefix, i)
    elif g_netmask_v6 == 126:
        for i in range(istart, iend, 4):
            for j in [1,2]:
                yield "%s:%.4x" % (ipprefix, i+j)
    else:
        print("Unsupported IPv6 subnet, valid values are 126 & 127")
        exit(0)

def give_loopback_v6():
    ip_split = g_loopback_ipv6.split(':')
    ipprefix = ':'.join(ip_split[:-1])
    lastoct = ip_split[-1]
    if not is_hex(lastoct):
        print("Unsupported IPv6 value, must have last octet as hex value")
        exit(0)
    istart = int(lastoct, 16)
    iend = int('ffff', 16)
    for i in range(istart, iend):
        if i in g_loopback_skip_octv6:
            continue
        yield "%s:%.4x" % (ipprefix, i)


def give_ipv4():
    if g_netmask_v4 != 31:
        print("Unsupported IPv4 subnet, valid value is 31")
        exit(0)
    ip_split = g_ipv4_start.split('.')
    ipprefix = '.'.join(ip_split[:-1])
    lastoct = int(ip_split[-1])
    for i in range(lastoct, 255, 2):
        yield "%s.%s,%s.%s" % (ipprefix, i, ipprefix, i + 1)


def give_loopback_v4():
    ip_split = g_loopback_ipv4.split('.')
    ipprefix = '.'.join(ip_split[:-1])
    lastoct = int(ip_split[-1])
    for i in range(lastoct, 255):
        if i in g_loopback_skip_octv4:
            continue
        yield "%s.%s" % (ipprefix, i)


def run_cmd(cmd, ignore_err=False):
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
################

if debug:
    run_cmd("switch \* debug-nvOS set-level xact")

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

# Enable jumbo frames on all ports
if g_jumbo_mtu:
    port_info = run_cmd("port-config-show format jumbo parsable-delim ,")
    if "on" not in port_info:
        _print("Enabling jumbo frames on all ports...", end='')
        sys.stdout.flush()
        run_cmd("switch \* port-config-modify port all disable", ignore_err=True)
        sleep(2)
        run_cmd("switch \* port-config-modify port all jumbo", ignore_err=True)
        sleep(2)
        run_cmd("switch \* port-config-modify port all enable", ignore_err=True)
        sleep(5)
        _print("Done")
        sys.stdout.flush()

# Get all the connected links - sw1,p1,p2,sw2
g_main_links = []
lldp_cmd = "lldp-show format switch,local-port,port-id,sys-name parsable-delim ,"
for conn in run_cmd(lldp_cmd):
    if not conn:
        _print("No LLDP output")
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
        _print("Disabling spine link on %s. Port: %s" % (sw1, p1))
        run_cmd("switch %s port-config-modify port %s disable" % (sw1, p1))
    # Get cluster node list
    if sw1 not in g_spine_list and sw2 not in g_spine_list:
        if (sw1, sw2) not in g_cluster_nodes \
            and (sw2, sw1) not in g_cluster_nodes:
            g_cluster_nodes.add((sw1, sw2))

_print("")
_print("### Configure Clusters/vRouters/Loopback-Interfaces", must_show=True)
_print("### ===============================================", must_show=True)
# Create Clusters
if len(g_cluster_nodes) == 0:
    _print("No cluster nodes found")
    exit(0)

existing_clusters = []
cluster_info = run_cmd("cluster-show format cluster-node-1,cluster-node-2 "
                       "parsable-delim ,")
for cinfo in cluster_info:
    if not cinfo:
        break
    nodes = cinfo.split(",")
    existing_clusters.append(tuple(nodes))

i = 1
for c_node in g_cluster_nodes:
    if c_node in existing_clusters:
        continue
    sw1, sw2 = c_node
    _print("Creating cluster: cluster-leaf%d between %s & %s" % (i, sw1, sw2))
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

loopbackv6_gen = give_loopback_v6()
# Create vRouters
for swname in g_fab_nodes:
    vrname = "%s-vrouter" % swname
    lpv6_ip = loopbackv6_gen.next()
    if vrname in existing_vrouters:
        continue
    _print("Creating vRouter %s on %s..." % (vrname, swname), end='')
    sys.stdout.flush()
    run_cmd("switch %s vrouter-create name %s vnet %s-global "
            "router-type hardware router-id %s proto-multi pim-ssm "
            "ospf-bfd-all-if ospf-redistribute none" % (
                swname, vrname, g_fab_name, g_rid_info[swname]))
    sleep(5)
    _print("Done")
    sys.stdout.flush()
    _print("Adding loopback-v4/v6 interface %s/%s on %s..." % (
            g_rid_info[swname], lpv6_ip, vrname), end='')
    sys.stdout.flush()
    run_cmd("switch %s vrouter-loopback-interface-add vrouter-name %s "
            "ip %s" % (swname, vrname, g_rid_info[swname]))
    sleep(1)
    run_cmd("switch %s vrouter-loopback-interface-add vrouter-name %s "
            "ip %s" % (swname, vrname, lpv6_ip))
    sleep(1)
    run_cmd("vrouter-ospf-add vrouter-name %s network %s/%s "
            "ospf-area 0" % (vrname, g_rid_info[swname], 32))
    _print("Done")
    sys.stdout.flush()
    run_cmd("vrouter-ospf6-add vrouter-name %s nic lo ospf6-area "
            "0.0.0.0" % vrname)

# Create L3 interfaces with IPv4/IPv6 addresssing
ipv4_generator = give_ipv4()
netmask4 = g_netmask_v4
ipv6_generator = give_ipv6()
netmask6 = g_netmask_v6

_print("")
_print("### Create L3 interfaces with IPv4/IPv6 addresssing", must_show=True)
_print("### ===============================================", must_show=True)
for link in g_l3_links:
    sw1, p1, p2, sw2 = link
    # Give lower ip to spine node
    if sw2 in g_spine_list:
        sw2, p2, p1, sw1 = sw1, p1, p2, sw2
    ipv4_1, ipv4_2 = ipv4_generator.next().split(',')
    ipv6_1 = ipv6_generator.next()
    ipv6_2 = ipv6_generator.next()
    #####vRouter-Interface#####
    _print("Adding vRouter interface to vrouter=%s-vrouter port=%s "
          "ipv4=%s/%s, ipv6=%s/%s..." % (sw1, p1, ipv4_1, netmask4,
                           ipv6_1, netmask6), end='')
    sys.stdout.flush()
    #run_cmd("switch %s port-config-modify port %s disable" % (sw1, p1))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip "
            "%s/%s ip2 %s/%s mtu %s" % (sw1, p1, ipv4_1, netmask4, ipv6_1,
                                        netmask6, g_mtu))
    #run_cmd("switch %s port-config-modify port %s enable" % (sw1, p1))
    _print("Done")
    sys.stdout.flush()
    sleep(5)
    ##### OSPFv4 #####
    _print("Adding OSPF for vrouter=%s-vrouter ipv4=%s..." % (
            sw1, ipv4_1), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
            "ospf-area 0" % (sw1, ipv4_1, netmask4))
    _print("Done")
    sys.stdout.flush()
    ##### OSPFv6 #####
    if show_only:
        temp, nic = 'xx', '<nic>'
    else:
        int_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter "
                           "format nic ip %s/%s parsable-delim ," % (
                                sw1, ipv4_1, netmask4))
        for v4_int in int_info:
            if not v4_int:
                _print("No IPv4 interfaces configured")
                exit(0)
            temp, nic = v4_int.split(',')
            break
    _print("Adding OSPF for IPv6 network on vrouter=%s-vrouter "
          "nic=%s..." % (sw1, nic), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf6-add vrouter-name %s-vrouter nic %s "
            "ospf6-area 0.0.0.0" % (sw1, nic))
    _print("Done")
    sys.stdout.flush()
    sleep(3)
    ########################################
    #####vRouter-Interface#####
    _print("Adding vRouter interface to vrouter=%s-vrouter port=%s "
          "ipv4=%s/%s ipv6=%s/%s..." % (sw2, p2, ipv4_2, netmask4, ipv6_2,
                                        netmask6), end='')
    sys.stdout.flush()
    #run_cmd("switch %s port-config-modify port %s disable" % (sw2, p2))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip "
            "%s/%s ip2 %s/%s mtu %s" % (sw2, p2, ipv4_2, netmask4, ipv6_2,
                                        netmask6, g_mtu))
    #run_cmd("switch %s port-config-modify port %s enable" % (sw2, p2))
    _print("Done")
    sys.stdout.flush()
    sleep(5)
    ##### OSPFv4 #####
    _print("Adding OSPF for vrouter=%s-vrouter ipv4=%s..." % (
            sw2, ipv4_2), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
            "ospf-area 0" % (sw2, ipv4_2, netmask4))
    _print("Done")
    sys.stdout.flush()
    ##### OSPFv6 #####
    if show_only:
        temp, nic = 'xx', '<nic>'
    else:
        int_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter "
                           "format nic ip %s/%s parsable-delim ," % (
                                sw2, ipv4_2, netmask4))
        for v4_int in int_info:
            if not v4_int:
                _print("No IPv4 interfaces configured")
                exit(0)
            temp, nic = v4_int.split(',')
            break
    _print("Adding OSPF for IPv6 network on vrouter=%s-vrouter "
          "nic=%s..." % (sw2, nic), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf6-add vrouter-name %s-vrouter nic %s "
            "ospf6-area 0.0.0.0" % (sw2, nic))
    _print("Done")
    sys.stdout.flush()
    sleep(3)
    ########################################

_print("")
_print("### Setup iOSPF Links", must_show=True)
_print("### =================", must_show=True)
for sws in g_cluster_nodes:
    sw1, sw2 = sws
    # Give lower ip to spine node
    if sw2 in g_spine_list:
        sw1, sw2 = sw2, sw1
    ####Creation cluster VLANs####
    _print("Creating VLAN 4040 cluster scope on switches: %s & %s..." % sws,
          end='')
    sys.stdout.flush()
    run_cmd("switch %s vlan-create id %s scope cluster" %
            (sw1, g_cluster_vlan))
    _print("Done")
    sys.stdout.flush()
    sleep(1)
    ########################################
    ipv4_1, ipv4_2 = ipv4_generator.next().split(',')
    ipv6_1 = ipv6_generator.next()
    ipv6_2 = ipv6_generator.next()
    ########################################
    #####vRouter-Interface#####
    _print("Adding vRouter interface to vrouter=%s-vrouter vlan=%s "
          "ipv4=%s/%s ipv6=%s/%s..." % (sw1, g_cluster_vlan, ipv4_1,
                                        netmask4, ipv6_1, netmask6), end='')
    sys.stdout.flush()
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter vlan %s "
            "ip %s/%s ip2 %s/%s pim-cluster mtu %s" % (
                sw1, g_cluster_vlan, ipv4_1, netmask4, ipv6_1, netmask6,
                g_mtu))
    _print("Done")
    sys.stdout.flush()
    sleep(5)
    ########################################
    ##### OSPFv4 #####
    _print("Adding OSPF for vrouter=%s-vrouter ipv4=%s..." % (
            sw1, ipv4_1), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
            "ospf-area 0" % (sw1, ipv4_1, netmask4))
    _print("Done")
    sys.stdout.flush()
    ##### OSPFv6 #####
    if show_only:
        temp, nic = 'xx', '<nic>'
    else:
        int_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter "
                           "format nic ip %s/%s parsable-delim ," % (
                                sw1, ipv4_1, netmask4))
        for v4_int in int_info:
            if not v4_int:
                _print("No IPv4 interfaces configured")
                exit(0)
            temp, nic = v4_int.split(',')
            break
    _print("Adding OSPF for IPv6 network on vrouter=%s-vrouter "
          "nic=%s..." % (sw1, nic), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf6-add vrouter-name %s-vrouter nic %s "
            "ospf6-area 0.0.0.0" % (sw1, nic))
    _print("Done")
    sys.stdout.flush()
    sleep(3)
    ########################################
    #####vRouter-Interface#####
    _print("Adding vRouter interface to vrouter=%s-vrouter vlan=%s "
          "ipv4=%s/%s ipv6=%s/%s..." %
          (sw2, g_cluster_vlan, ipv4_2, netmask4, ipv6_2, netmask6), end='')
    sys.stdout.flush()
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter vlan %s "
            "ip %s/%s ip2 %s/%s pim-cluster mtu %s" % (
                sw2, g_cluster_vlan, ipv4_2, netmask4, ipv6_2, netmask6,
                g_mtu))
    _print("Done")
    sys.stdout.flush()
    sleep(5)
    ##### OSPFv4 #####
    _print("Adding OSPF for vrouter=%s-vrouter ipv4=%s..." % (
            sw2, ipv4_2), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s-vrouter network %s/%s "
            "ospf-area 0" % (sw2, ipv4_2, netmask4))
    _print("Done")
    sys.stdout.flush()
    ##### OSPFv6 #####
    if show_only:
        temp, nic = 'xx', '<nic>'
    else:
        int_info = run_cmd("vrouter-interface-show vrouter-name %s-vrouter "
                           "format nic ip %s/%s parsable-delim ," % (
                                sw2, ipv4_2, netmask4))
        for v4_int in int_info:
            if not v4_int:
                _print("No IPv4 interfaces configured")
                exit(0)
            temp, nic = v4_int.split(',')
            break
    _print("Adding OSPF for IPv6 network on vrouter=%s-vrouter "
          "nic=%s..." % (sw2, nic), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf6-add vrouter-name %s-vrouter nic %s "
            "ospf6-area 0.0.0.0" % (sw2, nic))
    _print("Done")
    sys.stdout.flush()
    sleep(3)
    ########################################
_print("")

########################################
_print("Configuring COPP...", end='')
sys.stdout.flush()
run_cmd("cpu-class-modify name ospf hog-protect enable")
run_cmd("cpu-class-modify name bgp hog-protect enable")
run_cmd("cpu-class-modify name lacp hog-protect enable")
run_cmd("cpu-class-modify name vrrp hog-protect enable")
run_cmd("cpu-class-modify name local-subnet hog-protect enable")
run_cmd("cpu-class-modify name stp hog-protect enable")
run_cmd("cpu-class-modify name bfd hog-protect enable")
_print("Done")
sys.stdout.flush()
########################################
_print("")

############################################################################
g_vrrp_vlan = [112, 111]
for c_nodes in g_cluster_nodes:
    vrrp_vlan = g_vrrp_vlan.pop()
    vip = "%s.1.1.1/24" % vrrp_vlan
    ip1 = "%s.1.1.2/24" % vrrp_vlan
    ip2 = "%s.1.1.3/24" % vrrp_vlan

    vip_no_mask = vip.split("/")[0]
    ip1_no_mask = ip1.split("/")[0]
    ip2_no_mask = ip2.split("/")[0]

    sw1 = c_nodes[0]
    sw2 = c_nodes[1]

    vrname1 = "%s-vrouter" % sw1
    vrname2 = "%s-vrouter" % sw2


    print("Creating vrrp vlan cluster scoped: %s on %d" % (sw1, vrrp_vlan))
    run_cmd("switch %s vlan-create id %d scope cluster" % (sw1, vrrp_vlan))
    
    print("Creating VRRP IPv4 interfaces using:")
    print("    VIP=%s" % vip)
    print("    Primary IP=%s" % ip1)
    print("    Secondary IP=%s" % ip2)
    print("")
    
    run_cmd("vrouter-modify name %s hw-vrrp-id %d" % (vrname1, g_vrrp_id))
    run_cmd("vrouter-modify name %s hw-vrrp-id %d" % (vrname2, g_vrrp_id))
    ###################First Interface#########################################
    print("Creating interface with sw: %s, ip: %s, vlan-id: %s" % (
    sw1, ip1, vrrp_vlan))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s if "
        "data mtu %s" % (vrname1, ip1, vrrp_vlan, g_mtu))
    
    time.sleep(2)
    print("")
    
    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s ip %s "
    		"vlan %s format nic parsable-delim ," % (
    		    sw1, vrname1, ip1, vrrp_vlan))
    for intf in intf_info:
    	if not intf:
    	    print("No router interface exist")
    	    exit(0)
    	pintf_index = intf.split(',')[1]
    	break
    
    print("Setting vrrp-master interface with sw: %s, vip: %s, vlan-id: %s, "
      "vrrp-id: %s, vrrp-priority: %s" % (sw1, vip, vrrp_vlan,
    				      g_vrrp_id, g_prim_vrrp_pri))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s "
        "if data vrrp-id %s vrrp-primary %s vrrp-priority %s mtu %s" % (
    	vrname1, vip, vrrp_vlan, g_vrrp_id, pintf_index,
    	g_prim_vrrp_pri, g_mtu))
    
    time.sleep(2)
    print("")
    ########################-OSFP-##############################################
    print("Adding OSPF for IPv4 network on vrouter=%s network=%s/24 ospf-area "
      "0..." % (vrname1, vip), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s network %s ospf-area 0" % (
    	vrname1, vip))
    print("Done")
    sys.stdout.flush()
    print("")
    ########################-VTEP-##############################################
    print("Setup VTEP for %s-vrouter with ip %s and vip_no_mask %s" % (sw1,
	ip1_no_mask, vip_no_mask))
    run_cmd("vtep-create name %s-vtep location %s vrouter-name %s ip %s "
    	"virtual-ip %s" % (sw1, sw1, vrname1, ip1_no_mask, vip_no_mask))
    ###################Second Interface#########################################
    print("Creating interface with sw: %s, ip: %s, vlan-id: %s" % (
    sw2, ip2, vrrp_vlan))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s "
        "if data mtu %s" % (vrname2, ip2, vrrp_vlan, g_mtu))
    
    time.sleep(2)
    print("")
    
    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s ip %s "
    		"vlan %s format nic parsable-delim ," % (
    		    sw2, vrname2, ip2, vrrp_vlan))
    for intf in intf_info:
    	if not intf:
    	    print("No router interface exist")
    	    exit(0)
    	sintf_index = intf.split(',')[1]
    	break
    
    print("Setting vrrp-slave interface with sw: %s, vip: %s, vlan-id: %s, "
      "vrrp-id: %s, vrrp-priority: %s" % (sw2, vip, vrrp_vlan,
    				      g_vrrp_id, g_sec_vrrp_pri))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s if data "
        "vrrp-id %s vrrp-primary %s vrrp-priority %s mtu %s" % (
    	vrname2, vip, vrrp_vlan, g_vrrp_id, sintf_index,
    	g_sec_vrrp_pri, g_mtu))
    
    time.sleep(2)
    print("")
    ########################-OSFP-##############################################
    print("Adding OSPF for IPv4 network on vrouter=%s network=%s/24 ospf-area "
      "0..." % (vrname2, vip), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s network %s ospf-area 0" % (
    	vrname2, vip))
    print("Done")
    sys.stdout.flush()
    print("")
    ########################-VTEP-##############################################
    print("Setup VTEP for %s-vrouter with ip %s and vip_no_mask %s" % (sw2,
	ip2_no_mask, vip_no_mask))
    run_cmd("vtep-create name %s-vtep location %s vrouter-name %s ip %s "
    	"virtual-ip %s" % (sw2, sw2, vrname2, ip2_no_mask, vip_no_mask))
############################################################################

############################################################################
vrf_name = "tolly-vrf"
vlan_list = [120, 121]
vxlan_trunk_port = 44
print("Creating fabric VRF: %s" % (vrf_name))
run_cmd("vrf-create name %s scope fabric" % (vrf_name))
print("Setting up port %d for vxlan-loopback-trunk" % (vxlan_trunk_port))
run_cmd("switch \* trunk-modify name vxlan-loopback-trunk ports %d" % (vxlan_trunk_port))
for vlan in vlan_list:
	print("Creating VLAN: %d, VXLAN: %d00000" % (vlan, vlan))
	run_cmd("vlan-create id %d scope fabric vxlan %d00000" % (vlan, vlan))
	ip6 = "%d0:0db8:0001:0000:0000:0000:0000:0001" % vlan
	forward_ip6 = "%d0:0db8:0001:0000:0000:0000:0000:0100" % vlan
	print("Creating subnet for vlan %d, network %d.1.1.0/24, "
	      "anycast-gw-ip %d.1.1.1 network6 %s/64 anycast-gw-ip6 %s "
	      "packet-relay enable forward-proto dhcp forward-ip %d.1.1.100 "
	      "forward-ip6 %s" % (vlan, vlan, vlan, ip6, ip6, vlan, forward_ip6))
	run_cmd("subnet-create vxlan %d00000 network %d.1.1.0/24 vrf %s "
		"anycast-gw-ip %d.1.1.1 network6 %s/64 anycast-gw-ip6 %s "
		"packet-relay enable forward-proto dhcp forward-ip %d.1.1.100 "
		"forward-ip6 %s" % (vlan, vlan, vrf_name, vlan, ip6, ip6, vlan,
				    forward_ip6))
############################################################################

########################-VTEP-VXLAN-ADD##############################################
print("Setup VTEP for vrouters")
run_cmd("vtep-vxlan-add name leaf1-vtep vxlan 12000000")
run_cmd("vtep-vxlan-add name leaf2-vtep vxlan 12000000")
run_cmd("vtep-vxlan-add name leaf3-vtep vxlan 12000000")
run_cmd("vtep-vxlan-add name leaf4-vtep vxlan 12000000")
run_cmd("vtep-vxlan-add name leaf1-vtep vxlan 12100000")
run_cmd("vtep-vxlan-add name leaf2-vtep vxlan 12100000")
run_cmd("vtep-vxlan-add name leaf3-vtep vxlan 12100000")
run_cmd("vtep-vxlan-add name leaf4-vtep vxlan 12100000")
############################################################################