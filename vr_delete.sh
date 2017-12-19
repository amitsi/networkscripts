#!/bin/bash

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

### To delete all vrs
i=1
for ip in ${switches[@]}; do
        log "Deleting vrouter vr$i on switch $ip..."
        echo "test123" | sshpass -p test123 ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet "shell cli --quiet --no-login-prompt -e vrouter-delete name vr$i"
        let "i+=1"
        sleep 2
done
