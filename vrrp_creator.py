#!/usr/bin/python

""" PN VRRP Creation """

from __future__ import print_function
from binascii import hexlify
import subprocess
import argparse
import time
import sys
import re
import struct
import socket

##################
# Constants
##################
g_vrrp_id = 15
g_prim_vrrp_pri = 110
g_sec_vrrp_pri = 109

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='VRRP creator')
parser.add_argument(
    '-s', '--switch',
    help='list of switches separated by comma. Switch1 will become primary',
    required=True
)
parser.add_argument(
    '-v', '--vlan',
    help='VLAN ID',
    required=True
)
parser.add_argument(
    '--ipv4',
    help='IPv4 address in CIDR notation',
    required=False
)
parser.add_argument(
    '--ipv6',
    help='IPv6 address in CIDR notation',
    required=False
)
args = vars(parser.parse_args())

##################
# VALIDATIONs
##################

def validate_ipv4_cidr(ip):
    CIDR_RE = re.compile(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.)"
                         "{3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])"
                         "(\/([0-9]|[1-2][0-9]|3[0-2]))$")
    if CIDR_RE.match(ip):
        return True
    return False

def normalize_ipv6(ipcidr):
    # Split string into a list, example:
    #   '1080:200C::417A' => ['1080', '200C', '417A'] and fill_pos=2
    # and fill_pos is the position of '::' in the list
    ipstr, cidr = ipcidr.split('/')
    items = []
    index = 0
    fill_pos = None
    while index < len(ipstr):
        text = ipstr[index:]
        if text.startswith("::"):
            if fill_pos is not None:
                # Invalid IPv6, eg. '1::2::'
                raise ValueError("%r: Invalid IPv6 address: more than one "
                                 "'::'" % ipstr)
            fill_pos = len(items)
            index += 2
            continue
        pos = text.find(':')
        if pos == 0:
            # Invalid IPv6, eg. '1::2:'
            raise ValueError("%r: Invalid IPv6 address" % ipstr)
        if pos != -1:
            items.append(text[:pos])
            if text[pos:pos+2] == "::":
                index += pos
            else:
                index += pos+1

            if index == len(ipstr):
                # Invalid IPv6, eg. '1::2:'
                raise ValueError("%r: Invalid IPv6 address" % ipstr)
        else:
            items.append(text)
            break

    if items and '.' in items[-1]:
        # IPv6 ending with IPv4 like '::ffff:192.168.0.1'
        if (fill_pos is not None) and not (fill_pos <= len(items)-1):
            # Invalid IPv6: 'ffff:192.168.0.1::'
            raise ValueError("%r: Invalid IPv6 address: '::' after IPv4" % ipstr)
        value = parseAddress(items[-1])[0]
        items = items[:-1] + ["%04x" % (value >> 16), "%04x" % (value & 0xffff)]

    # Expand fill_pos to fill with '0'
    # ['1','2'] with fill_pos=1 => ['1', '0', '0', '0', '0', '0', '0', '2']
    if fill_pos is not None:
        diff = 8 - len(items)
        if diff <= 0:
            raise ValueError("%r: Invalid IPv6 address: '::' is not "
                             "needed" % ipstr)
        items = items[:fill_pos] + ['0']*diff + items[fill_pos:]

    # Here we have a list of 8 strings
    if len(items) != 8:
        # Invalid IPv6, eg. '1:2:3'
        raise ValueError("%r: Invalid IPv6 address: should have 8 "
                         "hextets" % ipstr)
    return ':'.join(items) + '/' + cidr

def validate_ipv6(ip):
    #: Regex for validating an IPv6 in hex notation
    HEX_RE = re.compile(r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$')
    #: Regex for validating an IPv6 in dotted-quad notation
    DQUAD_RE = re.compile(r'^([0-9a-f]{0,4}:){2,6}(\d{1,3}\.){0,3}\d{1,3}$')
    if HEX_RE.match(ip):
        return len(ip.split('::')) <= 2
    if DQUAD_RE.match(ip):
        halves = ip.split('::')
        if len(halves) > 2:
            return False
        hextets = ip.split(':')
        quads = hextets[-1].split('.')
        for q in quads:
            if int(q) > 255:
                return False
        return True
    return False

def validate_ipv6_cidr(ip_cidr):
    #: Regex for validating a CIDR network
    #CIDR_RE = re.compile(r'^([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}/\d{1,3}$')
    #if CIDR_RE.match(ip_cidr):
    ip, mask = ip_cidr.split('/')
    if validate_ipv6(ip):
        if int(mask) > 128:
            return False
    else:
        return False
    return True
    #return False

g_switch_list = [i.strip() for i in args['switch'].split(',')]
if len(g_switch_list) != 2:
    print("Incorrect number of switches specified. There must be 2 switches")
    exit(0)

g_ipv4_range = args['ipv4']
if not g_ipv4_range:
    set_ipv4 = False
else:
    if not validate_ipv4_cidr(g_ipv4_range):
        print("Incorrect IP address format. It should be in CIDR notation")
        exit(0)
    set_ipv4 = True

g_ipv6_range = args['ipv6']
if not g_ipv6_range:
    set_ipv6 = False
else:
    try:
        g_ipv6_range = normalize_ipv6(g_ipv6_range)
    except ValueError:
        exit(0)
    if not validate_ipv6_cidr(g_ipv6_range):
        print("Incorrect IPv6 address format. It should be in CIDR notation")
        exit(0)
    if not set_ipv4:
        print("Must specify ipv4 network to which this %s ipv6 network "
              "is to be added" % g_ipv6_range)
        exit(0)
    set_ipv6 = True
    set_ipv4 = False

g_vlan_id = args['vlan']
if not g_vlan_id.isdigit() or int(g_vlan_id) not in range(0, 4095):
    print("VLAN ID is incorrect")
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

def give_ipv4_ip(ip_cidr):
    (ip, cidr) = ip_cidr.split('/')
    host_bits = 32 - int(cidr)
    i = struct.unpack('>I', socket.inet_aton(ip))[0] # note the endianness
    start = i
    end = i | ((1 << host_bits) - 1)
    for i in range(start, end):
        yield socket.inet_ntoa(struct.pack('>I', i)) + '/' + cidr

def give_ipv6_ip(ip_cidr):
    MAX_IPV6 = (1 << 128) - 1
    (ip, cidr) = ip_cidr.split('/')
    host_bits = 128 - int(cidr)
    start = int(hexlify(socket.inet_pton(socket.AF_INET6, ip)), 16)
    end = start | ((1 << host_bits) - 1)
    for i in range(start, end):
        hex_str = '%032x' % i
        hextets = ['%x' % int(hex_str[x:x + 4], 16) for x in range(0, 32, 4)]
        yield ":".join(hextets) + '/' + cidr

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

# Validate switch list
for sw in g_switch_list:
    if sw not in g_fab_nodes:
        print("Incorrect switch name %s" % sw)
        exit(0)

# Validate routers
g_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,")
for vinfo in vrouter_info:
    if not vinfo:
        print("No vrouters found")
        exit(0)
    vr_name = vinfo
    g_vrouters.append(vr_name)
for sw in g_switch_list:
    if sw+"-vrouter" not in g_vrouters:
        print("Vrouter %s-vrouter doesn't exist" % sw)
        exit(0)

# Set VRRP ID for vrouters
print("Set VRRP ID %s for router %s-vrouter" % (
    g_vrrp_id, g_switch_list[0]))
run_cmd("vrouter-modify name %s-vrouter hw-vrrp-id %s" % (
    g_switch_list[0], g_vrrp_id))

print("Set VRRP ID %s for router %s-vrouter" % (g_vrrp_id, g_switch_list[1]))
run_cmd("vrouter-modify name %s-vrouter hw-vrrp-id %s" % (
    g_switch_list[1], g_vrrp_id))

time.sleep(2)
print("")

run_cmd("vlan-create id %s scope fabric" % g_vlan_id)
print("Created VLAN = %s" % g_vlan_id)

time.sleep(2)
print("")

##################

if set_ipv4:
    ip_gen = give_ipv4_ip(g_ipv4_range)
    try:
        vip = ip_gen.next()
        ip1 = ip_gen.next()
        ip2 = ip_gen.next()
    except StopIteration:
        print("Unable to generate more IPs from this range: %s" % g_ip_range)
        exit(0)

    ############################################################################
    print("Creating VRRP IPv4 interfaces using:")
    print("    VIP=%s" % vip)
    print("    Primary IP=%s" % ip1)
    print("    Secondary IP=%s" % ip2)
    print("")

    vrname1 = "%s-vrouter" % g_switch_list[0]
    vrname2 = "%s-vrouter" % g_switch_list[1]
    ###################First Interface#########################################
    print("Creating interface with sw: %s, ip: %s, vlan-id: %s" % (
        g_switch_list[0], ip1, g_vlan_id))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s if "
            "data" % (vrname1, ip1, g_vlan_id))

    time.sleep(2)
    print("")

    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s ip %s "
                        "vlan %s format nic parsable-delim ," % (
                            g_switch_list[0], vrname1, ip1, g_vlan_id))
    for intf in intf_info:
        if not intf:
            print("No router interface exist")
            exit(0)
        pintf_index = intf.split(',')[1]
        break

    print("Setting vrrp-master interface with sw: %s, vip: %s, vlan-id: %s, "
          "vrrp-id: %s, vrrp-priority: %s" % (g_switch_list[0], vip, g_vlan_id,
                                              g_vrrp_id, g_prim_vrrp_pri))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s "
            "if data vrrp-id %s vrrp-primary %s vrrp-priority %s" % (
                vrname1, vip, g_vlan_id, g_vrrp_id, pintf_index,
                g_prim_vrrp_pri))

    time.sleep(2)
    print("")
    ########################-OSFP-##############################################
    print("Adding OSPF for IPv4 network on vrouter=%s network=%s ospf-area "
          "0..." % (vrname1, g_ipv4_range), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s network %s ospf-area 0" % (
                vrname1, g_ipv4_range))
    print("Done")
    sys.stdout.flush()
    time.sleep(5)
    print("")
    ###################Second Interface#########################################
    print("Creating interface with sw: %s, ip: %s, vlan-id: %s" % (
        g_switch_list[1], ip2, g_vlan_id))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s "
            "if data" % (vrname2, ip2, g_vlan_id))

    time.sleep(2)
    print("")

    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s ip %s "
                        "vlan %s format nic parsable-delim ," % (
                            g_switch_list[1], vrname2, ip2, g_vlan_id))
    for intf in intf_info:
        if not intf:
            print("No router interface exist")
            exit(0)
        sintf_index = intf.split(',')[1]
        break

    print("Setting vrrp-slave interface with sw: %s, vip: %s, vlan-id: %s, "
          "vrrp-id: %s, vrrp-priority: %s" % (g_switch_list[1], vip, g_vlan_id,
                                              g_vrrp_id, g_sec_vrrp_pri))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s if data "
            "vrrp-id %s vrrp-primary %s vrrp-priority %s" % (
                vrname2, vip, g_vlan_id, g_vrrp_id, sintf_index,
                g_sec_vrrp_pri))

    time.sleep(2)
    print("")
    ########################-OSFP-##############################################
    print("Adding OSPF for IPv4 network on vrouter=%s network=%s ospf-area "
          "0..." % (vrname2, g_ipv4_range), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf-add vrouter-name %s network %s ospf-area 0" % (
                vrname2, g_ipv4_range))
    print("Done")
    sys.stdout.flush()
    time.sleep(5)
    ############################################################################

if set_ipv6:
    ipv6_gen = give_ipv6_ip(g_ipv6_range)
    try:
        vip = ipv6_gen.next()
        ip1 = ipv6_gen.next()
        ip2 = ipv6_gen.next()
    except StopIteration:
        print("Unable to generate more IPs from this range: %s" % g_ip_range)
        exit(0)
    ipv4_gen = give_ipv4_ip(g_ipv4_range)
    try:
        vip_v4 = ipv4_gen.next()
        ip1_v4 = ipv4_gen.next()
        ip2_v4 = ipv4_gen.next()
    except StopIteration:
        print("Incorrect IPv4 range specified: %s" % g_ip_range)
        exit(0)

    ############################################################################
    print("Creating VRRP IPv6 interfaces using:")
    print("    VIP=%s" % vip)
    print("    Primary IP=%s" % ip1)
    print("    Secondary IP=%s" % ip2)
    print("")

    vrname1 = "%s-vrouter" % g_switch_list[0]
    vrname2 = "%s-vrouter" % g_switch_list[1]
    ###################First Interface#########################################
    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s "
                        "ip %s format nic parsable-delim ," % (
                            g_switch_list[0], vrname1, ip1_v4)) 
    for intf in intf_info:
        if not intf:
            print("Incorrect IPv4 range specified, Master IP %s is "
                  "invalid" % ip1_v4)
            exit(0)
        intf_index = intf.split(',')[1]
        break
    print("Creating IPv6 interface with sw: %s, ip: %s" % (
        g_switch_list[0], ip1))
    run_cmd("vrouter-interface-ip-add vrouter-name %s nic %s "
            "ip %s" % (vrname1, intf_index, ip1))

    time.sleep(2)
    print("")

    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s "
                        "ip2 %s vlan %s format nic parsable-delim ," % (
                            g_switch_list[0], vrname1, ip1, g_vlan_id))
    for intf in intf_info:
        if not intf:
            print("No router interface exist")
            exit(0)
        pintf_index = intf.split(',')[1]
        break

    print("Setting vrrp-master interface with sw: %s, vip: %s, vlan-id: %s, "
          "vrrp-id: %s, vrrp-priority: %s" % (g_switch_list[0], vip, g_vlan_id,
                                              g_vrrp_id, g_prim_vrrp_pri))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s "
            "if data vrrp-id %s vrrp-primary %s vrrp-priority %s" % (
                vrname1, vip, g_vlan_id, g_vrrp_id, pintf_index,
                g_prim_vrrp_pri))

    time.sleep(2)
    print("")
    ########################-OSFP-##############################################
    print("Adding OSPF for IPv6 network on vrouter=%s nic=%s..." % (
              vrname1, intf_index), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf6-add vrouter-name %s nic %s ospf6-area 0.0.0.0" % (
                vrname1, intf_index))
    print("Done")
    sys.stdout.flush()
    time.sleep(5)
    print("")
    ###################Second Interface#########################################
    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s "
                        "ip %s format nic parsable-delim ," % (
                            g_switch_list[1], vrname2, ip2_v4)) 
    for intf in intf_info:
        if not intf:
            print("Incorrect IPv4 range specified, Master IP %s is "
                  "invalid" % ip2_v4)
            exit(0)
        intf_index = intf.split(',')[1]
        break
    print("Creating IPv6 interface with sw: %s, ip: %s" % (
        g_switch_list[1], ip2))
    run_cmd("vrouter-interface-ip-add vrouter-name %s nic %s "
            "ip %s" % (vrname2, intf_index, ip2))
    time.sleep(2)
    print("")

    intf_info = run_cmd("switch %s vrouter-interface-show vrouter-name %s "
                        "ip2 %s vlan %s format nic parsable-delim ," % (
                            g_switch_list[1], vrname2, ip2, g_vlan_id))
    for intf in intf_info:
        if not intf:
            print("No router interface exist")
            exit(0)
        sintf_index = intf.split(',')[1]
        break

    print("Setting vrrp-slave interface with sw: %s, vip: %s, vlan-id: %s, "
          "vrrp-id: %s, vrrp-priority: %s" % (g_switch_list[1], vip, g_vlan_id,
                                              g_vrrp_id, g_sec_vrrp_pri))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s if data "
            "vrrp-id %s vrrp-primary %s vrrp-priority %s" % (
                vrname2, vip, g_vlan_id, g_vrrp_id, sintf_index,
                g_sec_vrrp_pri))

    time.sleep(2)
    print("")
    ########################-OSFP-##############################################
    print("Adding OSPF for IPv6 network on vrouter=%s nic=%s..." % (
              vrname2, intf_index), end='')
    sys.stdout.flush()
    run_cmd("vrouter-ospf6-add vrouter-name %s nic %s ospf6-area 0.0.0.0" % (
                vrname2, intf_index))
    print("Done")
    sys.stdout.flush()
    time.sleep(5)
    ############################################################################
    print("DONE")
