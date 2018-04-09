#!/usr/bin/python

""" PN Connectivity Ping/SSH/SNMP Test """

from __future__ import print_function
import subprocess
import time
import sys
import signal

seed_switch = "10.14.30.13" # Used to access CLI
g_test_interval = 2 # in minutes

g_fmsg = []

def cmd_exists(cmd):
    return subprocess.call("type " + cmd, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

def sys_print(msg, nl=True):
    if nl:
        sys.stdout.write(msg)
        sys.stdout.write('\n')
    else:
        sys.stdout.write(msg)
    sys.stdout.flush()

def signal_handler(signal, frame):
        sys_print('Exiting...')
        sys.exit(0)

def enable_shell():
    run_cmd("switch-local role-modify name network-admin shell")

def print_err(msg):
    print(msg)
    sys.exit(0)

def run_cmd(cmd, shell=False, local=False, switch=seed_switch):
    if not local:
        cmd = ("sshpass -p test123 ssh -q -oStrictHostKeyChecking=no "
               "-oConnectTimeout=10 network-admin@%s -- --quiet %s%s "
               "2>&1" % (switch, "shell " if shell else "", cmd))
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print_err("Failed running cmd %s" % cmd)

def is_ipv6(ip_addr):
    if ":" in ip_addr:
        return True
    return False

def vr_ping_test(vrname, ip_addr):
    global g_fmsg
    message = run_cmd("vrouter-ping vrouter-name %s host-ip %s "
                      "count 1" % (vrname, ip_addr))

    message = '\n'.join(message)
    if ('unreachable' in message or 'Unreachable' in message or
            '100% packet loss' in message):
        g_fmsg.append(vrname + " ====> " + ip_addr + " = Ping failed")
        return False
    return True

def snmp_test(swname, ip_addr):
    global g_fmsg
    if is_ipv6(ip_addr):
        output = run_cmd("snmpwalk  -v2c -mAll -c football udp6:[%s] "
                         "2>&1 | head" % (ip_addr), shell=True, local=True)
    else:
        output = run_cmd("snmpwalk  -v2c -mAll -c football %s "
                         "2>&1 | head 2>&1" % (ip_addr), shell=True, local=True)

    if swname in ",".join(output):
        return True
    g_fmsg.append(swname + " ==== " + ip_addr + " = SNMP walk failed")
    return False

def ssh_test(swname, ip_addr):
    global g_fmsg
    output = run_cmd("hostname", switch=ip_addr, shell=True)
    if swname in ",".join(output):
        return True
    g_fmsg.append(swname + " ==== " + ip_addr + " = SSH failed")
    return False

def ping_test(swname, ip_addr):
    if is_ipv6(ip_addr):
        message = run_cmd("ping6 -c 1 %s" % (ip_addr), shell=True, local=True)
    else:
        message = run_cmd("ping -c 1 %s" % (ip_addr), shell=True, local=True)

    message = '\n'.join(message)
    if ('unreachable' in message or 'Unreachable' in message or
            '100% packet loss' in message):
        g_fmsg.append(swname + " ==== " + ip_addr + " = Ping failed")
        return False
    return True

def get_all_ips():
    ip_info = run_cmd("switch \\* switch-setup-show format switch-name,"
                      "mgmt-ip,mgmt-ip6,in-band-ip,in-band-ip6,loopback-ip,"
                      "loopback-ip6 layout horizontal parsable-delim ,")
    all_gips = {}
    for ips in ip_info:
        if not ips:
            print_err("No IPs found from switch-setup-show")
        swname,mgmt,mgmt6,inband,inband6,loopback,loopback6 = ips.split(',')
        if swname:
            all_gips[swname] = [mgmt,mgmt6,inband,inband6,loopback,loopback6]
    return all_gips

def get_vr_ips():
    vr_ips = {}
    intf_info = run_cmd("vrouter-interface-show format l3-port,ip,ip2 "
                        "parsable-delim ,")
    for intf in intf_info:
        if not intf:
            print_err("No router interface exists")
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

def print_header(test_name, link_type, nlinks, head=True, tail=True, swname=""):
    if head:
        sys_print("Performing %s test for %s: " % (test_name, link_type), nl=False)
    if tail:
        if swname:
            sys_print("    %s: " % swname, nl=False)
        sys_print("[%s]" % (" " * nlinks), nl=False)
        sys_print("\b" * (nlinks+1), nl=False) # return to start of line, after '['

def print_footer():
    sys_print("]")
    global g_fmsg
    if g_fmsg:
        sys_print("    Failed for following IPs:")
        for msg in g_fmsg:
            sys_print("        "+msg)
        g_fmsg = []

def perform_vr_tests(test_name, link_type, vr_ips):
    nlinks = len(vr_ips)
    print_header(test_name, link_type, nlinks)
    for vrname in vr_ips:
        sys_print("-", nl=False)
        for vr in vr_ips:
            for ip in vr_ips[vr]:
                vr_ping_test(vrname, ip)
    print_footer()

def perform_global_tests(test_name, link_type, gips, swname):
    nlinks = len(gips)
    print_header("", "", nlinks, head=False, swname=swname)
    for ip in gips:
        if ip:
            sys_print("-", nl=False)
            ping_test(swname, ip)
            ssh_test(swname, ip)
            snmp_test(swname, ip)
    print_footer()

def init():
    if not cmd_exists("sshpass"):
        print_err("Please install sshpass before running this module")
    signal.signal(signal.SIGINT, signal_handler)
    enable_shell()

if __name__ == '__main__':
    init();
    sys_print("Fetching all Mgmt IPs, In-Band IPs, Loopback IPs, l3 link IPs...", nl=False)
    vr_ips = get_vr_ips()
    all_gips = get_all_ips()
    sys_print("Done")
    vrlen = len(vr_ips)
    while(True):
        print_header("local ping/ssh/snmp", "all mgmt-v4/v6, "
                     "inband-v4/v6, loopback-v4/v6 ", 0, tail=False)
        sys_print("")
        for swname in all_gips:
            perform_global_tests("local ping/ssh/snmp", "all %s mgmt-v4/v6, "
                                 "inband-v4/v6, loopback-v4/v6 "
                                 "ips" % swname, all_gips[swname], swname)
        sys_print("")
        perform_vr_tests("ping", "all l3 links", vr_ips)
        sys_print("")
        sys_print("Waiting for %s minutes" % g_test_interval)
        time.sleep(60*g_test_interval)
