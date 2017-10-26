#!/usr/bin/python

from __future__ import print_function
import subprocess
import time

##################
show_only = False

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

##################

lo_info = run_cmd("vrouter-loopback-interface-show format ip parsable-delim ,")
for loinfo in lo_info:
    if not loinfo:
        print("No loopback interfaces found")
        exit(0)
    vrname,ip = loinfo.split(",")
    if len(ip) > 18:
        cidr = 128
    else:
        cidr = 32
    print("Adding ip %s/%s to hmplabpsq-we50500-vrouter" % (ip, cidr))
    run_cmd("vrouter-bgp-network-add vrouter-name hmplabpsq-we50500-vrouter "
            "network %s/%s" % (ip, cidr))
    sleep(2)
    print("Adding ip %s/%s to hmplabpsq-we50600-vrouter" % (ip, cidr))
    run_cmd("vrouter-bgp-network-add vrouter-name hmplabpsq-we50600-vrouter "
            "network %s/%s" % (ip, cidr))
    sleep(2)

##################
