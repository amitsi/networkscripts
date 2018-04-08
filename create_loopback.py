#!/usr/bin/python

from __future__ import print_function
import subprocess
import argparse
import time

##################

def run_cmd(cmd):
    #    print(cmd)
    #    return
    m_cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % m_cmd)
        exit(0)

def sleep(sec):
    time.sleep(sec)

##################

lo_info = run_cmd("vrouter-loopback-interface-show format ip parsable-delim ,")
for lo in lo_info:
    if not lo:
        print("No loopback ips found")
        exit(0)
    vrname,loip = lo.split(',')
    swname = vrname[:-8]
    print("%s: Adding loopback ip %s in global zone" % (swname, loip))
    if "." in loip:
        run_cmd("switch %s switch-setup-modify loopback-ip %s" % (swname, loip))
    else:
        run_cmd("switch %s switch-setup-modify loopback-ip6 %s" % (swname, loip))
    sleep(1)

################################################
print("DONE")
################################################
