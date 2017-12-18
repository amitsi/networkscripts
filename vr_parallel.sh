#!/bin/bash

FAIL=0

verizon_switches=(
        'tme-ara-spine1'
        'tme-ara-spine2'
        'tme-ara-spine3'
        'tme-ara-spine4'
        'tme-aquarius-leaf1'
        'tme-aquarius-leaf2'
        'tme-aquarius-leaf3'
        'tme-aquarius-leaf4'
        'tme-aquarius-leaf5'
        '10.13.26.204'
)

switches=(
        '10.110.0.160'
        '10.110.0.161'
        '10.110.0.162'
        '10.110.0.163'
        '10.110.0.164'
        '10.110.0.165'
)

gui_switches=(
        '10.110.0.81'
        '10.110.0.82'
        '10.110.0.83'
        '10.110.0.84'
        '10.110.0.85'
        '10.110.0.86'
)

function log() {
	echo "[$(date +%H:%M:%S)] $1"
}

log "Enabling XACT log"
sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@${switches[0]} -- --quiet "switch * debug-nvOS set-level xact"
sleep 1
log "Modifying reserve retry max to 0"
sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@${switches[0]} -- --quiet "switch * transaction-settings-modify reserve-retry-maximum 0"
sleep 1
log "Enabling shell access"
sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@${switches[0]} -- --quiet "switch * role-modify name network-admin shell"
sleep 1

fabname="$(sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@${switches[0]} -- --quiet fabric-info layout horizontal parsable-delim , format name)"

log "================================================================"
log "Please wait creating vrouters in parallel on all the switches..."
log "================================================================"

i=1
for ip in ${switches[@]}; do
        log "Creating vrouter vr$i on switch $ip..."
        echo "test123" | sshpass -p test123 ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet "shell cli --quiet vrouter-create name vr$i vnet $fabname-global" &
	let "i+=1"
done

for job in `jobs -p`
do
    wait $job || let "FAIL+=1"
done

log "==========================================="
if [ "$FAIL" == "0" ]; then
	log "All vrouters were successfully created :)"
else
	log "Some issue. Please try manually !"
fi
log "==========================================="

log "Modifying reserve retry max to 10"
sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@${switches[0]} -- --quiet "switch * transaction-settings-modify reserve-retry-maximum 10"
