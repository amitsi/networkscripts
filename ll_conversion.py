#!/usr/bin/python

from __future__ import print_function
import subprocess
import time
import argparse

parser = argparse.ArgumentParser(description='linklocal conversion')
parser.add_argument(
    '--show-only',
    help='will show commands it will run',
    action='store_true',
    required=False
)
args = vars(parser.parse_args())

show_only = args["show_only"]

def run_cmd(cmd):
    m_cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    if show_only and "-show" not in cmd:
        print(">>> " + cmd)
        return
    try:
        proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % m_cmd)
        exit(0)

def sleep(sec):
    if not show_only:
        time.sleep(sec)

def get_ll_ipv6(global_ipv6):
    global_ipv6 = global_ipv6.replace('::', ':')
    return "fe80:" + global_ipv6[4:]

intf_info = run_cmd("vrouter-interface-show format ip,ip2,linklocal,nic parsable-delim ,")
for intf in intf_info:
    if not intf:
        print("No vrouter interfaces found")
        exit(0)
    vrname,ip1,ip2,ll,nic = intf.split(",")
    if ":" in ip1:
        new_ll = get_ll_ipv6(ip1)
        run_cmd("vrouter-interface-ip-add vrouter-name %s nic %s ip %s" % (vrname, nic, new_ll))
    elif ":" in ip2:
        new_ll = get_ll_ipv6(ip2)
        run_cmd("vrouter-interface-ip-add vrouter-name %s nic %s ip %s" % (vrname, nic, new_ll))
    else:
        continue

################################################
print("DONE")
################################################
