#!/usr/bin/python

"""
Features:
* Full mesh ping to all l3/vlan-based interfaces
* Ping/SNMP/SSH test to all global IPs (Mgmt/Inband/Loopback)
* Tests IPv4 & IPv6 addresses
* Reports ping latency
* Skips disabled vrouters

Command:-
# python check_links.py -h
usage: check_links.py [-h] [-u USERNAME] [-p PASSWORD] -s SEED_SWITCH

Check-Links

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        seed switch username (default: network-admin)
  -p PASSWORD, --password PASSWORD
                        seed switch password (default: test123)
  -s SEED_SWITCH, --seed-switch SEED_SWITCH
                        fabric seed switch

Example Run:-
--snip--
# python check_links.py -s 10.14.30.11
[*] Checking reachability to seed switch...Done
[*] Enabling shell access on seed switch...Done
[*] Fetching all global IPs from 10.14.30.11...Done
[*] Fetching all l3/vlan-based link IPs from 10.14.30.11...Done

From local to mgmt-v4 IP 10.14.30.20 of switch ara-L3-01 :
  * Ping : Pass (ttl=64, time=0.148ms)
  * SSH  : Pass
  * SNMP : Fail

From local to mgmt-v6 IP 2721::ce37:abff:fed0:dc47 of switch ara-L3-01 :
  * Ping : Pass (ttl=64, time=1.07ms)
  * SSH  : Pass
  * SNMP : Fail

From local to inband-v4 IP 104.255.62.40 of switch ara-L3-01 :
  * Ping : Fail
  * SSH  : Pass
  * SNMP : Fail

.
.
.

[Ping] From dorado21-vrouter to all l3/vlan-based links of dorado19-vrouter :
  * 106.10.1.2 : Pass (ttl=64, time=2.07ms)
  * 62:4:12:1::2 : Pass (ttl=64, time=2.05ms)
  * 106.10.1.1 : Fail (interface is down)
  * 62:4:12:1::1 : Fail (interface is down)
  * 106.10.2.2 : Pass (ttl=64, time=2.14ms)
  * 62:4:12:2::2 : Pass (ttl=64, time=2.07ms)
  * 106.10.2.1 : Fail (interface is down)
  * 62:4:12:2::1 : Fail (interface is down)
  * 106.10.3.2 : Pass (ttl=64, time=2.31ms)
  * 62:4:12:3::2 : Pass (ttl=64, time=1.99ms)
--snip--
"""

from __future__ import print_function
import subprocess
import threading
import argparse
import signal
import time
import sys
import os

g_ping_interval = 3 # in minutes

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Check-Links')
parser.add_argument(
    '-u', '--username',
    help='seed switch username (default: network-admin)',
    required=False,
    default="network-admin"
)
parser.add_argument(
    '-p', '--password',
    help='seed switch password (default: test123)',
    required=False,
    default="test123"
)
parser.add_argument(
    '-s', '--seed-switch',
    help='fabric seed switch',
    required=True
)
args = vars(parser.parse_args())

class Spinner:
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in '|/-\\': yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay): self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def start(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def stop(self):
        self.busy = False
        time.sleep(self.delay)

class PNClass(object):

    def __init__(self, args):
        if not self.bin_exists("sshpass"):
            self.sys_exit("Please install sshpass to run this program")

        self.username = args["username"]
        self.password = args["password"]
        self.seed_switch = args["seed_switch"]

        signal.signal(signal.SIGINT, self.signal_handler)
        self.spinner = Spinner()

        self.sys_print("[*] Checking reachability to seed switch...", nl=False)
        self.spinner.start()
        result = self.ping_test(None, self.seed_switch, quiet=True)
        self.spinner.stop()
        if not result:
            self.sys_exit("Failed - %s is not reachable" % self.seed_switch)
        self.sys_print("Done")

        self.sys_print("[*] Enabling shell access on seed switch...", nl=False)
        self.spinner.start()
        self.enable_shell()
        self.spinner.stop()
        self.sys_print("Done")

        self.sys_print("[*] Fetching all global IPs from %s..." % self.seed_switch, nl=False)
        self.spinner.start()
        self.all_gips = self.get_all_ips()
        self.spinner.stop()
        self.sys_print("Done")

        self.sys_print("[*] Fetching all l3/vlan-based link IPs from %s..." % self.seed_switch, nl=False)
        self.spinner.start()
        self.vrs = self.get_vr()
        self.vr_ips = self.get_vr_ips()
        self.spinner.stop()
        self.sys_print("Done")

        self.sys_print()

    def sys_print(self, msg="", nl=True):
        if nl:
            sys.stdout.write(msg)
            sys.stdout.write('\n')
        else:
            sys.stdout.write(msg)
        sys.stdout.flush()

    def sys_exit(self, msg=None):
        if msg:
            self.sys_print(msg)
        sys.exit(0)

    def bin_exists(self, program):
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
                return True
        return False

    def signal_handler(self, signal, frame):
            self.sys_print('Exiting...', nl=False)
            self.sys_exit("Done")

    def enable_shell(self):
        self.run_cmd("switch-local role-modify name network-admin shell")

    def run_cmd(self, cmd, shell=False, local=False, other_switch=None):
        if other_switch:
            cmd_prefix = ("sshpass -p %s ssh -q -oStrictHostKeyChecking=no "
                          "-oConnectTimeout=10 %s@%s -- --quiet" % (
                          self.password, self.username, other_switch))
        elif self.seed_switch and not local:
            cmd_prefix = ("sshpass -p %s ssh -q -oStrictHostKeyChecking=no "
                          "-oConnectTimeout=10 %s@%s -- --quiet" % (
                          self.password, self.username, self.seed_switch))
        else:
            cmd_prefix = "cli"
        cmd_exec = "%s %s%s 2>&1" % (cmd_prefix, "shell " if shell else "", cmd)
        try:
            proc = subprocess.Popen(cmd_exec, shell=True, stdout=subprocess.PIPE)
            output = proc.communicate()[0]
            return output.strip().split('\n')
        except:
            self.spinner.busy = False
            self.sys_exit("Failed running cmd %s" % cmd)

    def is_ipv6(self, ip_addr):
        if ":" in ip_addr:
            return True
        return False

    def ping_test(self, vrname, ip_addr, local=False, quiet=False, l3_test=False):
        if not ip_addr:
            return

        if vrname:
            out = self.run_cmd("vrouter-ping vrouter-name %s host-ip %s "
                               "count 1" % (vrname, ip_addr))
        else:
            if self.is_ipv6(ip_addr):
                out = self.run_cmd("ping6 -c 1 %s" % (ip_addr), shell=True, local=local)
            else:
                out = self.run_cmd("ping -c 1 %s" % (ip_addr), shell=True, local=local)

        message = '\n'.join(out)
        if ('unreachable' in message or 'Unreachable' in message or
                '100% packet loss' in message):
            if quiet:
                return False
            if not l3_test:
                self.sys_print("  * Ping : Fail")
            else:
                self.sys_print("  * %s : Fail" % (ip_addr))
            return False
        if ('interface is down' in message):
            if quiet:
                return False
            if not l3_test:
                self.sys_print("  * Ping : Fail (interface is down)")
            else:
                self.sys_print("  * %s : Fail (interface is down)" % (ip_addr))
            return False
        info = []
        for msg in out:
            if "icmp_seq=" in msg:
                msg = msg.split()
                for m in msg:
                    if "ttl" in m:
                        info.append(m)
                    if "time" in m:
                        info.append(m + "ms")
                break
        if quiet:
            return True
        if not l3_test:
            if info:
                self.sys_print("  * Ping : Pass (%s)" % (", ".join(info)))
            else:
                self.sys_print("  * Ping : Pass")
        else:
            if info:
                self.sys_print("  * %s : Pass (%s)" % (ip_addr, ", ".join(info)))
            else:
                self.sys_print("  * %s : Pass" % (ip_addr))
        return True

    def snmp_test(self, swname, ip_addr):
        if self.is_ipv6(ip_addr):
            output = self.run_cmd("snmpwalk  -v2c -mAll -c football udp6:[%s] "
                                  "2>&1 | head" % (ip_addr), shell=True, local=True)
        else:
            output = self.run_cmd("snmpwalk  -v2c -mAll -c football %s "
                                  "2>&1 | head 2>&1" % (ip_addr), shell=True, local=True)

        if swname in ",".join(output):
            self.sys_print("  * SNMP : Pass")
            return True
        self.sys_print("  * SNMP : Fail")
        return False

    def ssh_test(self, swname, ip_addr):
        output = self.run_cmd("hostname", other_switch=ip_addr, shell=True)
        if swname in ",".join(output):
            self.sys_print("  * SSH  : Pass")
            return True
        self.sys_print("  * SSH  : Fail")
        return False

    def get_all_ips(self):
        ip_info = self.run_cmd("switch \\* switch-setup-show format switch-name,"
                               "mgmt-ip,mgmt-ip6,in-band-ip,in-band-ip6,loopback-ip,"
                               "loopback-ip6 layout horizontal parsable-delim ,")
        all_gips = {}
        for ips in ip_info:
            if not ips:
                self.sys_exit("No IPs found from switch-setup-show")
            swname,mgmt,mgmt6,inband,inband6,loopback,loopback6 = ips.split(',')
            if swname:
                all_gips[swname] = (mgmt,mgmt6,inband,inband6,loopback,loopback6)
        return all_gips

    def get_vr(self):
        vr_info = self.run_cmd("vrouter-show format name,state parsable-delim ,")
        vrs = {}
        for vr_info in vr_info:
            if not vr_info:
                self.sys_exit("No router exists")
            if ',' not in vr_info:
                continue
            vrname, state = vr_info.split(',')
            vrs[vrname] = state
        return vrs

    def get_vr_ips(self):
        intf_info = self.run_cmd("vrouter-interface-show format l3-port,ip,ip2,vrrp-state "
                                 "parsable-delim ,")
        vr_ips = {}
        for intf in intf_info:
            if not intf:
                self.sys_exit("No router interface exists")
            if ',' not in intf:
                continue
            vrname,l3_port,ip1_cidr,ip2_cidr,vrrp_state = intf.split(',')
            if vrrp_state == "slave":
                continue
            ip1 = ip1_cidr.split('/')[0]
            if vr_ips.get(vrname, None):
                vr_ips[vrname].append(ip1)
            else:
                vr_ips[vrname] = [ip1]
            if ip2_cidr:
                ip2 = ip2_cidr.split('/')[0]
                if vr_ips.get(vrname, None):
                    vr_ips[vrname].append(ip2)
                else:
                    vr_ips[vrname] = [ip2]
        return vr_ips

    def l3_tests(self):
        for vrname in self.vr_ips:
            if self.vrs[vrname] != "enabled":
                self.sys_print("[Note: Skipping vrouter %s as it is disabled ]" % (vrname))
                continue
            for vr in self.vr_ips:
                if vrname == vr:
                    continue
                else:
                    self.sys_print("[Ping] From %s to all l3/vlan-based links of %s :" % (vrname, vr), nl=True)
                    for ip in self.vr_ips[vr]:
                        self.ping_test(vrname, ip, l3_test=True)
                    self.sys_print()

    def global_tests(self):
        for swname in self.all_gips:
            mgmt,mgmt6,inband,inband6,loopback,loopback6 = self.all_gips[swname]
            if mgmt:
                self.sys_print("From local to mgmt-v4 IP %s of switch %s :" % (mgmt, swname))
                self.ping_test(None, mgmt)
                self.ssh_test(swname, mgmt)
                self.snmp_test(swname, mgmt)
                self.sys_print()
            if mgmt6:
                self.sys_print("From local to mgmt-v6 IP %s of switch %s :" % (mgmt6, swname))
                self.ping_test(None, mgmt6)
                self.ssh_test(swname, mgmt6)
                self.snmp_test(swname, mgmt6)
                self.sys_print()
            if inband:
                self.sys_print("From local to inband-v4 IP %s of switch %s :" % (inband, swname))
                self.ping_test(None, inband)
                self.ssh_test(swname, inband)
                self.snmp_test(swname, inband)
                self.sys_print()
            if inband6:
                self.sys_print("From local to inband-v6 IP %s of switch %s :" % (inband6, swname))
                self.ping_test(None, inband6)
                self.ssh_test(swname, inband6)
                self.snmp_test(swname, inband6)
                self.sys_print()
            if loopback:
                self.sys_print("From local to loopback-v4 IP %s of switch %s :" % (loopback, swname))
                self.ping_test(None, loopback)
                self.ssh_test(swname, loopback)
                self.snmp_test(swname, loopback)
                self.sys_print()
            if loopback6:
                self.sys_print("From local to loopback-v6 IP %s of switch %s :" % (loopback6, swname))
                self.ping_test(None, loopback6)
                self.ssh_test(swname, loopback6)
                self.snmp_test(swname, loopback6)
                self.sys_print()

pnc = PNClass(args)
pnc.global_tests()
pnc.l3_tests()
