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

def toggle(switch, toggle_ports, toggle_speed, port_speed, splitter_ports):
    """
    Method to toggle ports for topology discovery
    :return: The output messages for assignment.
    """
    print("### Toggling ports for switch %s, from %s to %s" % (
            switch, port_speed, toggle_speed))
    for speed in toggle_speed:
        # Check if the speed to be converted can be for all the ports
        # or just first port. For ex: 40 can only be set for first port
        # 25/10 can be set for all the ports if port speed is 100g.
        if int(port_speed.strip('g'))/int(speed.strip('g')) >= 4:
            is_splittable = True
        else:
            is_splittable = False
        local_ports = run_cmd('switch %s lldp-show format local-port '
                              'parsable-delim ,' % switch)
        _undiscovered_ports = sorted(list(set(toggle_ports) - set(local_ports)),
                                 key=lambda x: int(x))
        non_splittable_ports = []
        undiscovered_ports = []
        for _port in _undiscovered_ports:
            if splitter_ports.get(_port, 0) == 1:
                undiscovered_ports.append("%s-%s" % (_port, int(_port)+3))
            elif splitter_ports.get(_port, 0) == 0:
                undiscovered_ports.append(_port)
            else:
                # Skip intermediate splitter ports
                continue
            if not is_splittable :
                non_splittable_ports.append(_port)
        undiscovered_ports = ",".join(undiscovered_ports)

        print("%s(%s) >> Toggling ports %s to %s" % (
            switch, port_speed, undiscovered_ports, speed))
        run_cmd('switch %s port-config-modify port %s '
                'disable' % (switch, undiscovered_ports))
        if non_splittable_ports:
            non_splittable_ports = ",".join(non_splittable_ports)
            run_cmd('switch %s port-config-modify port %s '
                    'speed %s enable' % (switch, non_splittable_ports, speed))
        else:
            run_cmd('switch %s port-config-modify port %s '
                    'speed %s enable' % (switch, undiscovered_ports, speed))

        sleep(10)

    # Revert undiscovered ports back to their original speed
    local_ports = run_cmd('switch %s lldp-show format local-port '
                          'parsable-delim ,' % switch)
    _undiscovered_ports = sorted(list(set(toggle_ports) - set(local_ports)),
                             key=lambda x: int(x))
    disable_ports = []
    undiscovered_ports = []
    for _port in _undiscovered_ports:
        if splitter_ports.get(_port, 0) == 1:
            disable_ports.append("%s-%s" % (_port, int(_port)+3))
            undiscovered_ports.append(_port)
        elif splitter_ports.get(_port, 0) == 0:
            disable_ports.append(str(_port))
            undiscovered_ports.append(_port)
        else:
            # Skip intermediate splitter ports
            pass
    undiscovered_ports = ",".join(undiscovered_ports)
    disable_ports = ",".join(disable_ports)
    print("%s >> Reverting port speed of ports %s to %s" % (
            switch, undiscovered_ports, port_speed))
    run_cmd('switch %s port-config-modify port %s '
            'disable' % (switch, disable_ports))
    run_cmd('switch %s port-config-modify port %s '
            'speed %s enable' % (switch, undiscovered_ports, port_speed))

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

    all_next_ports = []
    for port_info in max_ports:
        if port_info:
            port, speed = port_info.strip().split(',')
            all_next_ports.append(str(int(port)+1))
            if g_toggle_ports.get(speed, None):
                g_toggle_ports[speed]['ports'].append(port)

    # Get info on splitter ports
    g_splitter_ports = {}
    all_next_ports = ','.join(all_next_ports)
    splitter_info = run_cmd('switch %s port-show port %s format port,bezel-port '
                         'parsable-delim ,' % (switch, all_next_ports))
    for sinfo in splitter_info:
        if not sinfo:
            break
        _port, _sinfo = sinfo.split(',')
        _port = int(_port)
        if '.2' in _sinfo:
            for i in range(4):
                g_splitter_ports[str(_port-1 + i)] = 1 + i

    for port_speed, port_info in g_toggle_ports.iteritems():
        if port_info['ports']:
            toggle(switch, port_info['ports'], port_info['speeds'], port_speed,
                   g_splitter_ports)

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
