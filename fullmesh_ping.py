#!/usr/bin/python

""" PN Vrouter Full Mesh Ping Test """

from __future__ import print_function
import subprocess
import time
import sys

g_ping_interval = 5 # in minutes

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

print("Fetching all l3 link IPs...", end='')
sys.stdout.flush()
vr_ips = get_vr_ips()
print("Done")
vrlen = len(vr_ips)
while(True):
    print("Performing ping test for all l3 links = ", end='')
    sys.stdout.write("[%s]" % (" " * vrlen))
    sys.stdout.flush()
    sys.stdout.write("\b" * (vrlen+1)) # return to start of line, after '['
    fmsg = []
    for vrname in vr_ips:
        sys.stdout.write("-")
        sys.stdout.flush()
        for vr in vr_ips:
            if vrname == vr:
                continue
            else:
                for ip in vr_ips[vr]:
                    if not is_reachable(vrname, ip):
                        fmsg.append(vrname + " ====> " + ip + " = Unreachable")
                    time.sleep(1)
    print("]")
    sys.stdout.flush()
    if fmsg:
        print("Failed for following IPs:")
        sys.stdout.flush()
        for msg in fmsg:
            print(msg)
            sys.stdout.flush()
    print("Waiting for %s minutes" % g_ping_interval)
    sys.stdout.flush()
    time.sleep(60*g_ping_interval)
