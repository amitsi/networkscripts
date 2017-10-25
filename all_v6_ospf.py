from __future__ import print_function
import subprocess
import argparse
import time
import sys

parser = argparse.ArgumentParser(description='VRRP creator')
parser.add_argument(
    '-s', '--switch',
    help='list of switches separated by comma. Switch1 will become primary',
    required=True
)
args = vars(parser.parse_args())

g_switch_list = [i.strip() for i in args['switch'].split(',')]

################

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

################

all_intf = run_cmd("vrouter-interface-ip-show format ip no-show-headers")
for intf in all_intf:
    if not intf:
        print("No interfaces found")
        exit(0)
    vrname,ip = intf.split()
    if len(ip) > 18:
        for swname in g_switch_list:
            vrname = "%s-vrouter" % swname
            print("Adding bgp network on %s for %s..." % (swname, ip))
            sys.stdout.flush()
            run_cmd("switch %s vrouter-bgp-network-add vrouter-name %s "
                    "network %s" % (swname, vrname, ip))
            time.sleep(2)
            print("Done")
            sys.stdout.flush()

################
