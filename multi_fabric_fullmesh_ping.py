#!/usr/bin/python

""" 
PN Multi Vrouter Full Mesh Ping Test

This script does full mesh ping between different Fabrics
It is dual stack capable
It will also report Ping Latency
Will Skip disabled vrouters

Example Run:-

@amitsingh  python multi_fabric_fullmesh_ping.py -s ghspine01 -r ghspine-ursa -v

Supported Options:-

python multi_fabric_fullmesh_ping.py -h
usage: multi_fabric_fullmesh_ping.py [-h] [-c COUNT] -s SEED_SWITCH
                                     [-r REMOTE_SEED_SWITCH] [-d] [-a] [-v]

Full Mesh Ping

optional arguments:
  -h, --help            show this help message and exit
  -c COUNT, --count COUNT
                        number of times to run this script
  -s SEED_SWITCH, --seed-switch SEED_SWITCH
                        fabric seed switch
  -r REMOTE_SEED_SWITCH, --remote-seed-switch REMOTE_SEED_SWITCH
                        remote fabric seed switch
  -d, --dual-stack      ping ipv6 interfaces as well
  -a, --all             ping all interfaces including vlan based interfaces
  -v, --verbose         verbose mode

"""

from __future__ import print_function
import subprocess
import time
import sys
import argparse
import signal
import os

g_ping_interval = 3 # in minutes

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Full Mesh Ping')
parser.add_argument(
    '-c', '--count',
    help='number of times to run this script',
    required=False,
    default=1
)
parser.add_argument(
    '-s', '--seed-switch',
    help='fabric seed switch',
    required=True
)
parser.add_argument(
    '-r', '--remote-seed-switch',
    help='remote fabric seed switch',
    required=False
)
parser.add_argument(
    '-d', '--dual-stack',
    help='ping ipv6 interfaces as well',
    action='store_true',
    required=False
)
parser.add_argument(
    '-a', '--all',
    help='ping all interfaces including vlan based interfaces',
    action='store_true',
    required=False
)
parser.add_argument(
    '-v', '--verbose',
    help='verbose mode',
    action='store_true',
    required=False
)
args = vars(parser.parse_args())

try:
    g_count = int(args["count"])
except:
    print("Invalid value passed to argument count")
    exit(0)

seed_switch = args["seed_switch"]

if args["remote_seed_switch"]:
    remote_seed_switch = args["remote_seed_switch"]
else:
    remote_seed_switch = None

if args["all"]:
    ping_all = True
else:
    ping_all = False

if args["dual_stack"]:
    dual_stack = True
else:
    dual_stack = False

def sys_write(msg):
    sys.stdout.write(msg)
    sys.stdout.flush()

def sys_print(msg, nl=True):
    if nl:
        print(msg)
    else:
        print(msg, end='')
    sys.stdout.flush()

def sys_exit(msg=None):
    if msg:
        sys_print(msg)
    exit(0)

def bin_exists(program):
    for path in os.environ["PATH"].split(os.pathsep):
        exe_file = os.path.join(path, program)
        if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
            return True
    return False

def run_cmd(cmd, switch=None):
    if switch:
        cmd_prefix = ("sshpass -p test123 ssh -q -oStrictHostKeyChecking=no "
                      "-oConnectTimeout=10 network-admin@%s " % (switch))
    else:
        cmd_prefix = "cli "
    cmd = cmd_prefix + cmd + " 2>/dev/null"
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        if ("Netvisor OS Command Line Interface" in output):
            output = output[output.index("Netvisor OS Command Line Interface"):]
        return output.strip().split('\n')
    except:
        sys_exit("Failed running cmd %s" % cmd)

def is_reachable(vrname, ip_addr, switch=None):
    if vrname:
        out = run_cmd("vrouter-ping vrouter-name %s host-ip %s "
                      "count 1" % (vrname, ip_addr), switch)
    else:
        out = run_cmd("ping -c 1 %s" % (ip_addr), switch)

    message = '\n'.join(out)
    info = []
    if ('unreachable' in message or 'Unreachable' in message or
            '100% packet loss' in message):
        return (False, info)
    for msg in out:
        if "icmp_seq=" in msg:
            msg = msg.split()
            for m in msg:
                if "ttl" in m:
                    info.append(m.replace("ttl", "nhops"))
                if "time" in m:
                    info.append(m + "(ms)")
            break
    return (True, info)

def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor

def get_vr(switch=None):
    vr_info = run_cmd("vrouter-show format name,state parsable-delim ,", switch)
    vrs = {}
    for vr_info in vr_info:
        if not vr_info:
            sys_exit("No router exists")
        if ',' not in vr_info:
            continue
        vrname, state = vr_info.split(',')
        vrs[vrname] = state
    return vrs

def get_vr_ips(switch=None):
    intf_info = run_cmd("vrouter-interface-show format l3-port,ip,%svrrp-state "
                        "parsable-delim ," % ("ip2," if dual_stack else ""), switch)
    vr_ips = {}
    for intf in intf_info:
        if not intf:
            sys_exit("No router interface exists")
        if ',' not in intf:
            continue
        if dual_stack:
            vrname,l3_port,ip1_cidr,ip2_cidr,vrrp_state = intf.split(',')
        else:
            vrname,l3_port,ip1_cidr,vrrp_state = intf.split(',')
        if vrrp_state == "slave":
            continue
        if not ping_all and not l3_port:
            continue
        ip1 = ip1_cidr.split('/')[0]
        if vr_ips.get(vrname, None):
            vr_ips[vrname].append(ip1)
        else:
            vr_ips[vrname] = [ip1]
        if dual_stack and ip2_cidr:
            ip2 = ip2_cidr.split('/')[0]
            if vr_ips.get(vrname, None):
                vr_ips[vrname].append(ip2)
            else:
                vr_ips[vrname] = [ip2]
    return vr_ips

def signal_handler(signal, frame):
        sys_write('Exiting...')
        sys_exit("Done")

def update_progress(vrname, fmsg, smsg):
    if fmsg:
        sys_print("Failure")
    else:
        sys_print("Success")
    if args["verbose"] and smsg:
        sys_print("  > Passed for following IPs:")
        for msg in smsg:
            sys_print(" "*4 + "* " + msg)
    if fmsg:
        sys_print("  > Failed for following IPs:")
        for msg in fmsg:
            sys_print(" "*4 + "* " + msg)

if not bin_exists("sshpass"):
    sys_exit("Please install sshpass to run this program")

result, _ = is_reachable(None, seed_switch)
if not result:
    sys_exit("Switch %s is not reachable" % seed_switch)

if remote_seed_switch:
    result, _ = is_reachable(None, remote_seed_switch)
    if not result:
        sys_exit("Switch %s is not reachable" % remote_seed_switch)

signal.signal(signal.SIGINT, signal_handler)
spinner = spinning_cursor()
sys_print("Fetching all l3 link IPs from %s..." % seed_switch, nl=False)
vrs = get_vr(seed_switch)
vr_ips = get_vr_ips(seed_switch)
sys_print("Done\n")
if remote_seed_switch:
    sys_print("Fetching all l3 link IPs from remote fabric switch "
              "%s..." % remote_seed_switch, nl=False)
    rem_vrs = get_vr(remote_seed_switch)
    rem_vr_ips = get_vr_ips(remote_seed_switch)
    sys_print("Done\n")
vrlen = len(vr_ips)
sys_print("Performing ping test:")
sys_print("=====================")
for _i in range(g_count):
    if _i > 0:
        sys_print("Waiting for %s minute(s)" % g_ping_interval)
        time.sleep(60*g_ping_interval)
    for vrname in vr_ips:
        if vrs[vrname] != "enabled":
            sys_print("  [Note: Skipping vrouter %s as it is disabled ]" % (vrname))
            continue
        sys_print("  From %s to all l3 links : " % (vrname), nl=False)
        fmsg = []
        smsg = []
        for vr in vr_ips:
            if vrname == vr:
                continue
            else:
                for ip in vr_ips[vr]:
                    sys_write(spinner.next())
                    result, info = is_reachable(vrname, ip, seed_switch)
                    if not result:
                        fail = True
                        fmsg.append(ip)
                    else:
                        if info:
                            smsg.append(ip + " - " + ", ".join(info))
                        else:
                            smsg.append(ip)
                    time.sleep(0.5)
                    sys_write('\b')
        update_progress(vrname, fmsg, smsg)
        if remote_seed_switch:
            for rem_vr in rem_vr_ips:
                fmsg = []
                smsg = []
                if rem_vrs[rem_vr] != "enabled":
                    sys_print("  [Note: Skipping remote fabric vrouter %s as it is disabled ]" % (rem_vr))
                    continue
                sys_print("  From %s to all l3 links of remote vrouter "
                          "%s: " % (vrname, rem_vr), nl=False)
                for ip in rem_vr_ips[rem_vr]:
                    sys_write(spinner.next())
                    result, info = is_reachable(vrname, ip, seed_switch)
                    if not result:
                        fail = True
                        fmsg.append(ip)
                    else:
                        if info:
                            smsg.append(ip + " - " + ", ".join(info))
                        else:
                            smsg.append(ip)
                    time.sleep(0.5)
                    sys_write('\b')
                update_progress(vrname, fmsg, smsg)
