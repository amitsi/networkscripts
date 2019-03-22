from __future__ import print_function
import subprocess
import argparse
import errno
import time
import sys

#===============================================================================
# ARGUMENT PARSING
#===============================================================================

parser = argparse.ArgumentParser(description='Multi-vRouter Setup Script')
parser.add_argument(
    '--swn-ip',
    help='IP for switch to multiple vrouters',
    required=True
)
parser.add_argument(
    '--sw1-ip',
    help='IP for switch to host 1 vrouter',
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
g_swn = args["swn_ip"]
g_sw1 = args["sw1_ip"]
g_vr_count = 32
g_ip_prefix = "192.168.1."
g_ip_netmask = "/30"
g_swn_as = 65000
g_sw1_as = 65035

#===============================================================================
# UTIL FUNCTIONS
#===============================================================================

def ignore_output_str(output):
    if "already" in output:
        return True
    if "exists" in output:
        return True
    return False

def run_local_cmd(cmd):
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print_err("Failed running cmd %s" % cmd)

def run_cmd(cmd, switch, ignore_err=False):
    ignore_err_list = [errno.EEXIST]
    m_cmd = ("sshpass -p test123 ssh -q -oStrictHostKeyChecking=no "
       "-oConnectTimeout=10 network-admin@%s -- --quiet %s "
       "2>&1" % (switch, cmd))
    if show_only and "-show" in cmd:
        return []
    if show_only and "-show" not in cmd:
        print("### " + cmd)
        return
    try:
        proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
        output,err = proc.communicate()
        if not ignore_err and \
           proc.returncode and \
           proc.returncode not in ignore_err_list and \
           not ignore_output_str(output):
            print("Failed running cmd %s (rc:%d)" % (m_cmd, proc.returncode))
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

def sort_str(l):
    """ Sort the given iterable in the way that humans expect."""
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    return sorted(l, key = alphanum_key)

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
    sys.stdout.flush()


#===============================================================================
# Multi-vRouter & Single-vRouter Configuration
#===============================================================================
existing_vnets = []
vnet_info = run_cmd("vnet-show format name parsable-delim ,", g_swn)
for vinfo in vnet_info:
    if not vinfo:
        break
    vn_name = vinfo
    existing_vnets.append(vn_name)

existing_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,", g_swn)
for vinfo in vrouter_info:
    if not vinfo:
        break
    vr_name = vinfo
    existing_vrouters.append(vr_name)

_print("")
_print("### Configuring %d vRouters" % g_vr_count, must_show=True)
_print("### =======================", must_show=True)

vlan_ip_as_list = []
ipindex = 1
swn_as = g_swn_as

for vr_index in range(1, g_vr_count+1):
    vnname = "vnet" + str(vr_index)
    if vnname not in existing_vnets:
        _print("Creating vNET %s on %s..." % (vnname, g_swn), end='')
        run_cmd("vnet-create name %s scope fabric" % (vnname), g_swn)
        sleep(1)
        _print("Done")

    vrname = "vr" + str(vr_index)
    if vrname in existing_vrouters:
        _print("vRouter %s already exists on %s" % (vrname, g_swn))
        continue
    _print("Creating vRouter %s on %s..." % (vrname, g_swn), end='')
    run_cmd("vrouter-create name %s vnet %s "
            "router-type hardware" % (vrname, vnname), g_swn)
    sleep(1)
    _print("Done")

    vlan_id = 100 + vr_index
    _print("Creating vlan, local scoped: %d on %s" % (vlan_id, g_swn))
    run_cmd("vlan-create id %d scope local" % (vlan_id), g_swn)
    sleep(1)
    _print("Done")

    vr_ip = g_ip_prefix + str(ipindex) + g_ip_netmask
    vr_neigh_ip = g_ip_prefix + str(ipindex+1)
    swn_as += 1
    _print("Creating interface on vrouter %s with ip %s & vlan %s on "
            "switch %s" % (vrname, vr_ip, vlan_id, g_swn))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s" % (
        vrname, vr_ip, vlan_id), g_swn)
    sleep(1)
    _print("Done")
    vlan_ip_as_list.append((vlan_id, ipindex+1, swn_as))
    ipindex += 4

    _print("Setting vRouter BGP-AS (%d) on %s..." % (swn_as, vrname), end='')
    run_cmd("vrouter-modify name %s bgp-as %d" % (vrname, swn_as), g_swn)
    sleep(1)
    _print("Done")

    _print("Adding bgp neighbor on %s for %s on switch %s..." % (
        vrname, vr_neigh_ip, g_swn))
    run_cmd("vrouter-bgp-add vrouter-name %s neighbor %s "
            "remote-as %d" % (vrname, vr_neigh_ip, g_sw1_as), g_sw1)
    sleep(2)
    _print("Done")
    _print("")

    _print("Adding bgp network on %s for %s on switch %s..." % (
        vrname, vr_ip, g_swn))
    run_cmd("vrouter-bgp-network-add vrouter-name %s "
            "network %s" % (vrname, vr_ip), g_swn)
    sleep(2)
    _print("Done")
    _print("")

#===============================================================================
existing_vnets = []
vnet_info = run_cmd("vnet-show format name parsable-delim ,", g_sw1)
for vinfo in vnet_info:
    if not vinfo:
        break
    vn_name = vinfo
    existing_vnets.append(vn_name)

existing_vrouters = []
vrouter_info = run_cmd("vrouter-show format name parsable-delim ,", g_sw1)
for vinfo in vrouter_info:
    if not vinfo:
        break
    vr_name = vinfo
    existing_vrouters.append(vr_name)
_print("")
_print("### Configuring single vRouter", must_show=True)
_print("### ==========================", must_show=True)

vnname = "vn"
if vnname not in existing_vnets:
    _print("Creating vNET %s on %s..." % (vnname, g_sw1), end='')
    run_cmd("vnet-create name %s scope fabric" % (vnname), g_sw1)
    sleep(1)
    _print("Done")

vrname = "vr"
if vrname not in existing_vrouters:
    _print("Creating vRouter %s on %s..." % (vrname, g_sw1), end='')
    run_cmd("vrouter-create name %s vnet %s "
            "router-type hardware" % (vrname, vnname), g_sw1)
    sleep(1)
    _print("Done")

_print("Setting vRouter BGP-AS (%d) on %s..." % (g_sw1_as, vrname), end='')
run_cmd("vrouter-modify name %s bgp-as %d" % (vrname, g_sw1_as), g_sw1)
sleep(1)
_print("Done")
_print("")

for entry in vlan_ip_as_list:
    vlan_id, ipindex, swn_as = entry
    _print("Creating vlan, local scoped: %d on %s" % (vlan_id, g_sw1))
    run_cmd("vlan-create id %d scope local" % (vlan_id), g_sw1)
    sleep(1)
    _print("Done")

    vr_ip = g_ip_prefix + str(ipindex) + g_ip_netmask
    vr_neigh_ip = g_ip_prefix + str(ipindex-1)
    _print("Creating interface on vrouter %s with ip %s & vlan %s on "
            "switch %s" % (vrname, vr_ip, vlan_id, g_sw1))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s" % (
        vrname, vr_ip, vlan_id), g_sw1)
    sleep(1)
    _print("Done")

    _print("Adding bgp neighbor on %s for %s on switch %s..." % (
        vrname, vr_neigh_ip, g_sw1))
    run_cmd("vrouter-bgp-add vrouter-name %s neighbor %s "
            "remote-as %d" % (vrname, vr_neigh_ip, swn_as), g_sw1)
    sleep(2)
    _print("Done")

    _print("Adding bgp network on %s for %s on switch %s..." % (
        vrname, vr_ip, g_sw1))
    run_cmd("vrouter-bgp-network-add vrouter-name %s "
            "network %s" % (vrname, vr_ip), g_sw1)
    sleep(2)
    _print("Done")
    _print("")

#===============================================================================
