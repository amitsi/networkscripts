#!/usr/bin/python

from __future__ import print_function
import argparse
import subprocess
import time
import sys
import re

##################
# ARGUMENT PARSING
##################

parser = argparse.ArgumentParser(description='Toggle ports')
parser.add_argument(
    '--switch',
    help='specific switch to run on',
    required=False
)
parser.add_argument(
    '--show-only',
    help='will show commands it will run',
    action='store_true',
    required=False
)
args = vars(parser.parse_args())

show_only = args["show_only"]
specific_switch = args["switch"]

##################

def run_cmd(cmd, ignore_err=True):
    m_cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    if show_only and "-show" not in cmd:
        print("### " + cmd)
        return
    try:
        proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        if not ignore_err and \
           proc.returncode and \
           proc.returncode not in ignore_err_list:
            print("Failed running cmd %s" % m_cmd)
            print("Retrying in 5 seconds....")
            sys.stdout.flush()
            time.sleep(5)
            proc = subprocess.Popen(m_cmd, shell=True, stdout=subprocess.PIPE)
            output = proc.communicate()[0]
            if proc.returncode:
                print("Failed again... Giving up !")
                exit(1)
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % m_cmd)
        exit(0)


def sleep(sec):
    if not show_only:
        time.sleep(sec)

##################

def toggle(switch, toggle_ports, toggle_speed, port_speed, max_ports):
    """
    Method to toggle ports for topology discovery
    :return: The output messages for assignment.
    """
    print("### Toggling ports for switch %s, from %s to %s" % (
            sw_name, port_speed, toggle_speed))
    ports_to_modify = []
    for speed in toggle_speed:
        local_ports = run_cmd('switch %s lldp-show format local-port '
                              'parsable-delim ,' % switch)
        ports_to_modify = sorted(list(set(toggle_ports) - set(local_ports)),
                                 key=lambda x: int(x))
        ports_to_modify = ",".join(ports_to_modify)

        print("%s(%s) >> Toggling ports %s to %s" % (
            switch, port_speed, ports_to_modify, speed))
        run_cmd('switch %s port-config-modify port %s '
                'disable' % (switch, ports_to_modify))
        run_cmd('switch %s port-config-modify port %s '
                'speed %s' % (switch, ports_to_modify, speed))
        run_cmd('switch %s port-config-modify port %s '
                'enable' % (switch, ports_to_modify))

        sleep(10)

    # Revert undiscovered ports back to their original speed
    local_ports = run_cmd('switch %s lldp-show format local-port '
                          'parsable-delim ,' % switch)
    ports_to_modify = list(set(toggle_ports) - set(local_ports))
    next_ports = ",".join([str(int(i) + 1) for i in ports_to_modify])
    bezel_info = run_cmd('switch %s port-show port %s format port,bezel-port '
                         'parsable-delim ,' % (switch, next_ports))
    bezel_ports = []
    non_bezel_ports = []
    for binfo in bezel_info:
        if not binfo:
            break 
        _port, _binfo = binfo.split(',')
        _port = int(_port)
        if '.2' in _binfo:
            bezel_ports.append("%s-%s" % (_port-1, _port+2))
        else:
            non_bezel_ports.append(str(_port-1))
    ports_to_modify = ",".join(sorted(ports_to_modify, key=lambda x: int(x)))
    bezel_ports = ",".join(bezel_ports)
    non_bezel_ports = ",".join(non_bezel_ports)
    print("%s >> Reverting port speed of ports %s to %s" % (
            switch, ports_to_modify, port_speed))
    if bezel_ports:
        run_cmd('switch %s port-config-modify port %s '
                'disable' % (switch, bezel_ports))
    if non_bezel_ports:
        run_cmd('switch %s port-config-modify port %s '
                'disable' % (switch, non_bezel_ports))
    run_cmd('switch %s port-config-modify port %s '
            'speed %s' % (switch, ports_to_modify, port_speed))
    run_cmd('switch %s port-config-modify port %s '
            'enable' % (switch, ports_to_modify))

def toggle_ports(switch):
    """
    Toggle 40g/100g ports for topology discovery
    """
    g_toggle_ports = {
        '25g': {'ports': [], 'speeds': ['10g']},
        '40g': {'ports': [], 'speeds': ['10g']},
        '100g': {'ports': [], 'speeds': ['10g', '25g', '40g']}
    }
    ports_25g = []
    ports_40g = []
    ports_100g = []
    max_ports = run_cmd('switch %s port-config-show format port,speed '
                        'parsable-delim ,' % switch)

    for port_info in max_ports:
        if port_info:
            port, speed = port_info.strip().split(',')
            if g_toggle_ports.get(speed, None):
                g_toggle_ports[speed]['ports'].append(port)

    for port_speed, port_info in g_toggle_ports.iteritems():
        if port_info['ports']:
            toggle(switch, port_info['ports'], port_info['speeds'], port_speed,
                   max_ports)

##################
# Get list of fabric nodes
g_fab_nodes = []
fab_info = run_cmd("fabric-node-show format name parsable-delim ,")
for sw_name in fab_info:
    if not sw_name:
        print("No fabric output")
        exit(0)
    g_fab_nodes.append(sw_name)

if specific_switch:
    if specific_switch not in g_fab_nodes:
        print("Switch %s is not part of this fabric" % specific_switch)
        exit(1)
    toggle_ports(specific_switch)
else:
    [toggle_ports(sw) for sw in g_fab_nodes]
