from __future__ import print_function
import subprocess
import time
import sys

################
# UTIL FUNCTIONS
################

def give_ip(start, end):
    tag = "2607:f4a0:3:0:250:56ff:feac:"
    for i in range(start,end,4):
        yield "%s%.4x,%s%.4x" %(tag,i+1,tag,i+2)

def run_cmd(cmd):
    cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" %cmd)
        exit(0)

def same_switch_type(sw_types, sw1, sw2):
    for group in sw_types.values():
        if sw1 in group and sw2 in group:
            return True
    return False

################

# Create vRouters
sw_cmd = "fabric-node-show format name,fab-name parsable-delim ,"
sw_details = run_cmd(sw_cmd)
for swinfo in sw_details:
    swname, fabname = swinfo.split(',')
    print("Creating vRouter %s-vrouter on %s..." %(swname, swname), end='')
    sys.stdout.flush()
    run_cmd("switch %s vrouter-create name %s-vrouter vnet %s-global router-type hardware" %(swname, swname, fabname))
    print("Done")
    sys.stdout.flush()
    time.sleep(2)

# Get Switch Grouping
sw_list = run_cmd("switch-info-show format switch,model layout horizontal parsable-delim ,")
sw_types = {}
for sw in sw_list:
    swname, swtype = sw.split(',')
    if sw_types.get(swtype, None):
        sw_types[swtype].append(swname)
    else:
        sw_types[swtype] = [swname]

# Enable all ports to get better visibility of the topology
run_cmd("switch \* port-config-modify port all enable")
run_cmd("switch \* stp-modify disable")

# Get Connected Links (not part of cluster)
links = []
lldp_cmd = "lldp-show format switch,local-port,port-id,sys-name parsable-delim ,"
for conn in run_cmd(lldp_cmd):
    sw1,p1,p2,sw2 = conn.split(',')
    # Skip Clustered links
    if same_switch_type(sw_types, sw1, sw2):
        continue
    if (sw2,p2,p1,sw1) not in links:
        links.append((sw1,p1,p2,sw2))

# Create L3 interfaces with IPv6 addresssing
ip_generator = give_ip(15360,15380)
for link in links:
    sw1,p1,p2,sw2 = link
    ip1,ip2 = ip_generator.next().split(',')
    print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s..." %(sw1, p1, ip1), end='')
    sys.stdout.flush()
    run_cmd("switch %s port-config-modify port %s disable" %(sw1, p1))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/126" %(sw1,p1,ip1))
    run_cmd("switch %s port-config-modify port %s enable" %(sw1, p1))
    print("Done")
    sys.stdout.flush()
    print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s..." %(sw2, p2, ip2), end='')
    sys.stdout.flush()
    run_cmd("switch %s port-config-modify port %s disable" %(sw2, p2))
    run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/126" %(sw2,p2,ip2))
    run_cmd("switch %s port-config-modify port %s enable" %(sw2, p2))
    print("Done")
    sys.stdout.flush()
