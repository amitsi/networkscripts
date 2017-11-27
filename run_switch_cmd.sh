#!/bin/bash

USER="root"
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

ansible_switches=(
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

PS3='Which setup do you want to reset? Please enter your choice: '
options=("Ansible" "GUI" "Verizon" "Quit")
select opt in "${options[@]}"
do
    case $opt in
        "Ansible")
            switches=("${ansible_switches[@]}")
            break
            ;;
        "GUI")
            switches=("${gui_switches[@]}")
            break
            ;;
        "Verizon")
            switches=("${verizon_switches[@]}")
            break
            ;;
        "Quit")
	    exit 0
            ;;
        *) echo invalid option;;
    esac
done
read -p "Enter the cmd to run = " -r
echo    # (optional) move to a new line
if [[ -z $REPLY ]]; then
	exit 0
fi

PARALLEL=0
if [[ $1 = "-p" ]]; then
	PARALLEL=1
fi

function run_cmd() {
	output=$(sshpass -p "test123" ssh -q -oStrictHostKeyChecking=no $USER@$ip -- "$REPLY")
	ping -c 1 $1 -W 2 > /dev/null
	if [[ $? -ne 0 ]]; then
		echo "$1 - Unreachable"
		continue
	fi
	nc -z $1 22 -w 2
	if [[ $? -ne 0 ]]; then
		echo "$1 - Unable to SSH"
		continue
	fi
	echo "$1 - $output"
	sleep 1
}

if [[ $PARALLEL -eq 1 ]]; then
	FAIL=0
	for ip in ${switches[@]}; do
		run_cmd $ip &
	done
	for job in `jobs -p`
	do
	    wait $job || let "FAIL+=1"
	done

	echo "==========================================="
	if [ "$FAIL" == "0" ]; then
		echo "Cmd ran successfully on all switches :)"
	else
		echo "Some issue. Please try sequentially !"
	fi
	echo "==========================================="
else
	for ip in ${switches[@]}; do
		echo "----------------------------------"
		echo "Switch : $ip"
		echo "----------------------------------"
		ping -c 1 $ip -W 2 > /dev/null
		if [[ $? -ne 0 ]]; then
			echo "Switch: $ip - Unreachable"
			echo "----------------------------------"
			continue
		fi
		nc -z $ip 22 -w 2
		if [[ $? -ne 0 ]]; then
			echo "Switch: $ip - Unable to SSH"
			echo "----------------------------------"
			continue
		fi
		sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no $USER@$ip --  "$REPLY"
	done
fi
