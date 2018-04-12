#!/usr/bin/python

""" PN Vrouter Full Mesh Ping Test """

from __future__ import print_function
import subprocess
import time
import sys
import argparse
import signal

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
args = vars(parser.parse_args())

try:
    g_count = int(args["count"])
except:
    print("Invalid value passed to argument count")
    exit(0)

def run_cmd(cmd):
    cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % cmd)
        exit(0)

def is_reachable(vrname, ip_addr):
    message = run_cmd("vrouter-ping vrouter-name %s host-ip %s "
                      "count 1" % (vrname, ip_addr))

    message = '\n'.join(message)
    if ('unreachable' in message or 'Unreachable' in message or
            '100% packet loss' in message):
        return False
    return True

def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor

def get_vr_ips():
    intf_info = run_cmd("vrouter-interface-show format l3-port,ip,ip2 "
                        "parsable-delim ,")
    vr_ips = {}
    for intf in intf_info:
        if not intf:
            print("No router interface exists")
            exit(0)
        vrname,l3_port,ip1_cidr,ip2_cidr = intf.split(',')
        if l3_port:
            ip1 = ip1_cidr.split('/')[0]
            ip2 = None
            if ip2_cidr:
                ip2 = ip2_cidr.split('/')[0]
            if vr_ips.get(vrname, None):
                vr_ips[vrname].append(ip1)
                if ip2:
                    vr_ips[vrname].append(ip2)
            else:
                vr_ips[vrname] = [ip1]
                if ip2:
                    vr_ips[vrname].append(ip2)
    return vr_ips

def signal_handler(signal, frame):
        sys.stdout.write('Exiting...')
        sys.stdout.flush()
        print("Done")
        sys.stdout.flush()
        exit(0)

def update_progress(vrname, fmsg):
    if fmsg:
        print("Failure")
        sys.stdout.flush()
        print("  > Failed for following IPs:")
        sys.stdout.flush()
        for msg in fmsg:
            print(" "*4 + "* " + msg)
            sys.stdout.flush()
    else:
        print("Success")
        sys.stdout.flush()

signal.signal(signal.SIGINT, signal_handler)
spinner = spinning_cursor()
print("Fetching all l3 link IPs...", end='')
sys.stdout.flush()
vr_ips = get_vr_ips()
print("Done\n")
vrlen = len(vr_ips)
print("Performing ping test:")
print("=====================")
for _i in range(g_count):
    if _i > 0:
        print("Waiting for %s minute(s)" % g_ping_interval)
        sys.stdout.flush()
        time.sleep(60*g_ping_interval)
    for vrname in vr_ips:
        print("  From " + vrname + " to all l3 links : ", end='')
        sys.stdout.flush()
        fmsg = []
        for vr in vr_ips:
            if vrname == vr:
                continue
            else:
                for ip in vr_ips[vr]:
                    sys.stdout.write(spinner.next())
                    sys.stdout.flush()
                    if not is_reachable(vrname, ip):
                        fail = True
                        fmsg.append(ip)
                    time.sleep(0.5)
                    sys.stdout.write('\b')
        update_progress(vrname, fmsg)
