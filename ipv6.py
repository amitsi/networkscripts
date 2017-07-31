from __future__ import print_function
import subprocess
import time

def give_ip(start, end):
        tag = "2607:f4a0:3:0:250:56ff:feac:"
        for i in range(start,end,4):
                yield "%s%.4x,%s%.4x" %(tag,i+1,tag,i+2)

def run_cmd(cmd, output=True):
        cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
        try:
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
                output = proc.communicate()[0]
                return output.strip().split('\n')
        except:
                print("Failed running cmd %s" %cmd)
                exit(0)

# Create vRouters
sw_cmd = "fabric-node-show format name,fab-name parsable-delim ,"
sw_details = run_cmd(sw_cmd)
for swinfo in sw_details:
        swname, fabname = swinfo.split(',')
        print("Creating vRouter %s-vrouter on %s..." %(swname, swname), end='')
        run_cmd("switch %s vrouter-create name %s-vrouter vnet %s-global router-type hardware" %(swname, swname, fabname))
        print("Done")
        time.sleep(2)

# Create L3 interfaces with IPv6 addresssing
ip_generator = give_ip(15360,15380)
lldp_cmd = "lldp-show format switch,local-port,port-id,sys-name no-show-headers parsable-delim ,"
for conn in run_cmd(lldp_cmd):
        sw1,p1,p2,sw2 = conn.split(',')
        ip1,ip2 = ip_generator.next().split(',')
        print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s..." %(sw1, p1, ip1), end='')
        run_cmd("switch %s port-config-modify port %s disable" %(sw1, p1))
        run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/126" %(sw1,p1,ip1))
        run_cmd("switch %s port-config-modify port %s enable" %(sw1, p1))
        print("Done")
        print("Adding vRouter interface to vrouter=%s-vrouter port=%s ip=%s..." %(sw2, p2, ip2), end='')
        run_cmd("switch %s port-config-modify port %s disable" %(sw2, p2))
        run_cmd("vrouter-interface-add vrouter-name %s-vrouter l3-port %s ip %s/126" %(sw2,p2,ip2))
        run_cmd("switch %s port-config-modify port %s enable" %(sw2, p2))
        print("Done")
