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

#===============================================================================
# UTIL FUNCTIONS
#===============================================================================

def ping_test(ip_addr):
    cmd = ("ping -c 1 %s" % (ip_addr))

    message = run_local_cmd(cmd)
    message = '\n'.join(message)
    if ('0.0% packet loss' in message):
        return True
    return False

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
if not ping_test(g_swn):
    print("Switch %s is not reachable" % g_swn)
    exit(0)
if not ping_test(g_sw1):
    print("Switch %s is not reachable" % g_sw1)
    exit(0)

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

g_vlan_ipindex_list = []
ipindex = 1

for vr_index in range(1, g_vr_count+1):
    vnname = g_swn + "-vn-" + str(vr_index)
    if vnname not in existing_vnets:
        _print("Creating vNET %s on %s..." % (vnname, g_swn), end='')
        run_cmd("switch %s vnet-create name %s scope fabric" % (
                    g_swn, vnname), g_swn)
        sleep(1)
        _print("Done")

    vrname = g_swn + "-vr-" + str(vr_index)
    if vrname in existing_vrouters:
        _print("vRouter %s already exists on %s" % (vrname, g_swn))
        continue
    _print("Creating vRouter %s on %s..." % (vrname, g_swn), end='')
    run_cmd("switch %s vrouter-create name %s vnet %s "
            "router-type hardware" % (g_swn, vrname, vnname), g_swn)
    sleep(1)
    _print("Done")

    vlan_id = 100 + vr_index
    _print("Creating vlan, local scoped: %d on %s" % (vlan_id, g_swn))
    run_cmd("switch %s vlan-create id %d scope local" % (g_swn, vlan_id), g_swn)
    sleep(1)
    _print("Done")

    vr_ip = g_ip_prefix + str(ipindex) + g_ip_netmask
    _print("Creating interface on vrouter %s with ip %s & vlan %s on "
            "switch %s" % (vrname, vr_ip, vlan_id, g_swn))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s" % (
        vrname, vr_ip, vlan_id), g_swn)
    sleep(1)
    _print("Done")
    g_vlan_ipindex_list.append((vlan_id, ipindex+1))
    ipindex += 4

    _print("Adding bgp network on %s for %s on switch %s..." % (
        vrname, vr_ip, g_swn))
    run_cmd("switch %s vrouter-bgp-network-add vrouter-name %s "
            "network %s" % (g_swn, vrname, vr_ip), g_swn)
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

vnname = g_sw1 + "-vn"
if vnname not in existing_vnets:
    _print("Creating vNET %s on %s..." % (vnname, g_sw1), end='')
    run_cmd("switch %s vnet-create name %s scope fabric" % (
                g_sw1, vnname), g_sw1)
    sleep(1)
    _print("Done")

vrname = g_sw1 + "-vr"
if vrname not in existing_vrouters:
    _print("Creating vRouter %s on %s..." % (vrname, g_sw1), end='')
    run_cmd("switch %s vrouter-create name %s vnet %s "
            "router-type hardware" % (g_sw1, vrname, vnname), g_sw1)
    sleep(1)
    _print("Done")

for entry in g_vlan_ipindex_list:
    vlan_id, ipindex = entry
    _print("Creating vlan, local scoped: %d on %s" % (vlan_id, g_sw1))
    run_cmd("switch %s vlan-create id %d scope local" % (g_sw1, vlan_id), g_sw1)
    sleep(1)
    _print("Done")

    vr_ip = g_ip_prefix + str(ipindex) + g_ip_netmask
    _print("Creating interface on vrouter %s with ip %s & vlan %s on "
            "switch %s" % (vrname, vr_ip, vlan_id, g_sw1))
    run_cmd("vrouter-interface-add vrouter-name %s ip %s vlan %s" % (
        vrname, vr_ip, vlan_id), g_sw1)
    sleep(1)
    _print("Done")

    _print("Adding bgp network on %s for %s on switch %s..." % (
        vrname, vr_ip, g_sw1))
    run_cmd("switch %s vrouter-bgp-network-add vrouter-name %s "
            "network %s" % (g_sw1, vrname, vr_ip), g_sw1)
    sleep(2)
    _print("Done")
    _print("")

#===============================================================================
