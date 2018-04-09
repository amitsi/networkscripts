#!/usr/bin/python

from __future__ import print_function
import subprocess
import argparse
import time

##################

def run_cmd(cmd):
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

cf_info = run_cmd("vrouter-interface-config-show ospf-passive-if format "
                  "nic parsable-delim , | grep 40[0-9][1-9]")
for cf in cf_info:
    if not cf:
        print("No non-ospf-passive config found")
        exit(0)
    vrname,nic = cf.split(',')
    swname = vrname[:-8]
    print("Modifying config for %s, nic %s to ospf-passive false" % (vrname, nic))
    run_cmd("vrouter-interface-config-modify vrouter-name %s nic "
            "%s no-ospf-passive-if" % (vrname, nic))
    sleep(1)

################################################
print("DONE")
################################################
