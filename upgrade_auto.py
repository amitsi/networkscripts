from __future__ import print_function
import subprocess
import re

BASEURL = "http://sandy:8081/artifactory/offline-pkgs/onvl/nvOS-3.0.0/"
TEN_MINS = 10 * 60
THIRTY_MINS = 30 * 60
THREE_HRS = 3 * 60 * 60
OSPF_CNT = OSPF6_CNT = 24

def run_cmd(cmd, shell=False):
    if not shell:
        cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % cmd)
        exit(0)

def perror(msg):
    print(msg)
    exit(0)

def notify(msg):
    print(msg)

def uptime_to_mtime(time_str):
    time_int = 0
    for i in re.findall("(\d+[dhms])", time_str):
        if 'd' in i:
            time_int += int(i.split('d')[0]) * 24 * 60 * 60
        elif 'h' in i:
            time_int += int(i.split('h')[0]) * 60 * 60
        elif 'm' in i:
            time_int += int(i.split('m')[0]) * 60
        elif 's' in i:
            time_int += int(i.split('s')[0])
        else:
            perror("invalid time format %s" % time_str)
    return time_int

def fetch_sw_uptime():
    switch_time = run_cmd("system-stats-show format switch,uptime parsable-delim ,")
    sw_uptime = {}
    for sw_time in switch_time:
        if not sw_time:
            perror("Unable to fetch switches's uptime")
        sw, uptime = sw_time.split(',')
        sw_uptime[sw] = uptime_to_mtime(uptime)
    return sw_uptime

def do_upgrade():
    for vers in run_cmd("nvversion", shell=True):
        if not vers:
            perror("Unable to fetch switch nvOS version")
        from_vers = vers.split(",")[0]
        from_long_vers = int(vers.split(",")[0].split(".")[2])

    to_vers = ""
    pkg_cmd = ("curl -s -X GET -u ashish:AP6vE67gMPApLZtb6DJyUeUfqpz %s | "
               "grep 'pkg<' | cut -d ' ' -f 2 | cut -c 7-36 | sort" % BASEURL)
    for pkg in run_cmd(pkg_cmd, shell=True):
        if not pkg:
            perror("Unable to fetch pkg list from artifactory")
        long_vers = int(pkg.split("-")[2])
        if from_long_vers < long_vers:
            to_vers = "-".join(pkg.split("-")[1:3])
            pkg_url = BASEURL + pkg

    if not to_vers:
        perror("No pkgs with higher nvOS version found")

    notify("Downloading pkg from %s..." % pkg_url)
    run_cmd("rm /sftp/import/*; wget -qP /sftp/import %s" % pkg_url, shell=True)

    notify("Upgrading:  %s -> %s..." % (from_vers, to_vers))

def do_l3_checks():
    ospfv4 = False
    ospfv6 = False
    c_ospfv4 = run_cmd("vrouter-ospf-neighbor-show count-output | grep Count")
    for count in c_ospfv4:
        if count:
            if int(count.split(" ")[1]) == OSPF_CNT:
                ospfv4 = True
    c_ospfv6 = run_cmd("vrouter-ospf6-neighbor-show count-output | grep Count")
    for count in c_ospfv6:
        if count:
            if int(count.split(" ")[1]) == OSPF6_CNT:
                ospfv6 = True
    if not ospfv4:
        notify("OSPFv4 neighbor count doesn't match to %d" % OSPF_CNT)
    if not ospfv6:
        notify("OSPFv6 neighbor count doesn't match to %d" % OSPF6_CNT)
