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
    '--swn',
    help='switch to multiple vrouters',
    required=True
)
parser.add_argument(
    '--sw1',
    help='switch to host 1 vrouter',
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
g_swn = args["swn"]
g_sw1 = args["sw1"]
g_vr_count = 32
g_ip_prefix = "192.168.1."
g_ip_netmask = "/30"

#===============================================================================
# UTIL FUNCTIONS
#===============================================================================

def ignore_output_str(output):
    if "already" in output:
        return True
    if "exists" in output:
        return True
    return False

def run_cmd(cmd, ignore_err=False):
    ignore_err_list = [errno.EEXIST]
    m_cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    if show_only and "-show" not in cmd:
        print("### " + cmd)
        return
    try:
        proc = subprocess.Popen(m_cmd + " 2>&1", shell=True, stdout=subprocess.PIPE)
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

# Validate switches
if g_swn not in g_fab_nodes:
    print("Switch %s is not in fabric %s" % (g_swn, g_fab_name))
    exit(0)
if g_sw1 not in g_fab_nodes:
    print("Switch %s is not in fabric %s" % (g_sw1, g_fab_name))
    exit(0)

#===============================================================================
# Multi-vRouter & Single-vRouter Configuration
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
_print("### Configuring %d vRouters" % g_vr_count, must_show=True)
_print("### =======================", must_show=True)

g_vlan_ipindex_list = []
ipindex = 1

for vr_index in range(1, g_vr_count+1):
    vnname = g_swn + "-vn-" + str(vr_index)
    if vnname not in existing_vnets:
        _print("Creating vNET %s on %s..." % (vnname, g_swn), end='')
        run_cmd("switch %s vnet-create name %s scope fabric" % (
                    g_swn, vnname))
        sleep(1)
        _print("Done")

    vrname = g_swn + "-vr-" + str(vr_index)
    if vrname in existing_vrouters:
        _print("vRouter %s already exists on %s" % (vrname, g_swn))
        continue
    _print("Creating vRouter %s on %s..." % (vrname, g_swn), end='')
    run_cmd("switch %s vrouter-create name %s vnet %s "
            "router-type hardware" % (g_swn, vrname, vnname))
    sleep(1)
    _print("Done")

    vlan_id = 100 + vr_index
    _print("Creating vlan, local scoped: %d on %s" % (vlan_id, g_swn))
    run_cmd("switch %s vlan-create id %d scope local" % (g_swn, vlan_id))
    sleep(1)
    _print("Done")

    vr_ip = g_ip_prefix + str(ipindex) + g_ip_netmask
    _print("Creating interface on vrouter %s with ip %s & vlan %s on "
            "switch %s" % (vrname, vr_ip, vlan_id, g_swn))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s" % (
        vrname, vr_ip, vlan_id))
    sleep(1)
    _print("Done")
    g_vlan_ipindex_list.append((vlan_id, ipindex+1))
    ipindex += 4

    _print("Adding bgp network on %s for %s on switch %s..." % (
        vrname, vr_ip, g_swn))
    run_cmd("switch %s vrouter-bgp-network-add vrouter-name %s "
            "network %s" % (g_swn, vrname, vr_ip))
    sleep(2)
    _print("Done")
    _print("")

#===============================================================================
_print("")
_print("### Configuring single vRouter", must_show=True)
_print("### ==========================", must_show=True)

vnname = g_sw1 + "-vn"
if vnname not in existing_vnets:
    _print("Creating vNET %s on %s..." % (vnname, g_sw1), end='')
    run_cmd("switch %s vnet-create name %s scope fabric" % (
                g_sw1, vnname))
    sleep(1)
    _print("Done")

vrname = g_sw1 + "-vr"
if vrname not in existing_vrouters:
    _print("Creating vRouter %s on %s..." % (vrname, g_sw1), end='')
    run_cmd("switch %s vrouter-create name %s vnet %s "
            "router-type hardware" % (g_sw1, vrname, vnname))
    sleep(1)
    _print("Done")

for entry in g_vlan_ipindex_list:
    vlan_id, ipindex = entry
    _print("Creating vlan, local scoped: %d on %s" % (vlan_id, g_sw1))
    run_cmd("switch %s vlan-create id %d scope local" % (g_sw1, vlan_id))
    sleep(1)
    _print("Done")

    vr_ip = g_ip_prefix + str(ipindex) + g_ip_netmask
    _print("Creating interface on vrouter %s with ip %s & vlan %s on "
            "switch %s" % (vrname, vr_ip, vlan_id, g_sw1))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s" % (
        vrname, vr_ip, vlan_id))
    sleep(1)
    _print("Done")

    _print("Adding bgp network on %s for %s on switch %s..." % (
        vrname, vr_ip, g_sw1))
    run_cmd("switch %s vrouter-bgp-network-add vrouter-name %s "
            "network %s" % (g_sw1, vrname, vr_ip))
    sleep(2)
    _print("Done")
    _print("")

#===============================================================================
