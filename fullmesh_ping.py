#!/usr/bin/python

""" PN Vrouter Full Mesh Ping Test """

from __future__ import print_function
import subprocess
import logging
import time

g_ping_interval = 5 # in minutes

logger = logging.getLogger('fullmesh-ping')
hdlr = logging.FileHandler('/var/tmp/fullmesh_ping.log')
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.WARNING)

def run_cmd(cmd):
    cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % cmd)
        exit(0)

def run_ping_command(vrname, ip_addr):
    message = run_cmd("vrouter-ping vrouter-name %s host-ip %s "
                      "count 1" % (vrname, ip_addr))

    if ('unreachable' in message or 'Unreachable' in message or
            '100% packet loss' in message):
        logger.error("vrouter-ping failed from vrouter %s to ip "
                     "%s " % (vrname, ip_addr))


logger.warn("Starting vrouter full mesh ping test")
intf_info = run_cmd("vrouter-interface-show format l3-port,ip "
                    "parsable-delim ,")
while(True):
    for intf in intf_info:
        if not intf:
            logger.error("No router interface exists")
            exit(0)
        vrname,l3_port,ip_cidr = intf.split(',')
        if l3_port:
            ipaddr = ip_cidr.split('/')[0]
            run_ping_command(vrname, ipaddr)
            time.sleep(1)
    time.sleep(60*g_ping_interval)
