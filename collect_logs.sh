#!/bin/bash

REBOOT_CNT=2
USER=network-admin

switches=(
    '10.13.27.221'
    '10.13.27.218'
    '10.13.27.220'
    '10.13.27.219'
    '10.13.27.217'
    '10.13.27.216'
    '10.13.27.173'
    '10.13.26.21'
    '10.13.27.178'
    '10.13.27.185'
)

function printout() {
	echo "[$( date +'%Y-%m-%d %H:%M:%S' )] $1"
}

function run_cli() {
    sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no $USER@$1 -- --quiet $2
}

function run_shell() {
    echo "test123" | sshpass -p test123 ssh -q -oStrictHostKeyChecking=no $USER@$1 -- --quiet "shell sudo -S -- sh -c '$2' 2>/dev/null"
}

function is_reachable() {
    ping -c 1 $1 > /dev/null
    if [[ $? -ne 0 ]]; then
        echo "$1> Unreachable"
        return 1
    fi
    nc -w 2 -z $1 22 2>/dev/null
    if [[ $? -ne 0 ]]; then
        echo "$1> Unable to SSH"
        return 1
    fi
    run_cli $1 "switch-local switch-setup-show format mgmt-ip" | grep $1 > /dev/null
    if [[ $? -ne 0 ]]; then
        echo "$1> Unable to login via $USER"
        return 1
    fi
}

function collect_logs() {
    ip=$1
    cnt=$2
    fname="$ip.out.$cnt"
    printout "$ip> Collecting logs to $fname"
    echo "====================" > $fname
    echo "Running config show:" >> $fname
    echo "====================" >> $fname
    run_cli $ip "switch-local running-config-show" | grep -v "import-password" >> $fname
    echo "" >> $fname
    echo "" >> $fname
    echo "======================" >> $fname
    echo "Global interface list:" >> $fname
    echo "======================" >> $fname
    run_shell $ip "ip addr show" | grep "^[0-9]" | awk '{print $2}' >> $fname
    echo "" >> $fname
    echo "" >> $fname
    containers=($(run_shell $ip "lxc-ls -1"))
    for cont in ${containers[@]}; do
        c_dash=$(printf "%${#cont}s")
        echo "==========================${c_dash// /=}" >> $fname
        echo "Container interface list: $cont" >> $fname
        echo "==========================${c_dash// /=}" >> $fname
        run_shell $ip "lxc-attach -n $cont -- ip addr show" | grep "^[0-9]" | awk '{print $2}' >> $fname
        echo "" >> $fname
        echo "" >> $fname
    done
}

function reboot_sw() {
    ip=$1
    printout "$ip> Rebooting"
    run_shell $ip reboot 2>/dev/null
    sleep 10
    for (( rcnt=0; rcnt<200; cnt++ )); do
        is_reachable $ip >/dev/null
        if [[ $? -ne 0 ]]; then
            sleep 1
        else
            sleep 30
            printout "$ip> Up"
            break
        fi
    done
    if [[ $rcnt == 200 ]]; then
        printout "$ip> Unreachable after reboot"
        exit 1
    fi
}

function get_diff() {
    for ip in ${switches[@]}; do
	old_cnt=$(($1-1))
	old_fname="$ip.out.$old_cnt"
	new_fname="$ip.out.$1"
	diff_fname="$ip.$old_cnt-$1.diff"
	printout "$ip> Collecting diff in $diff_fname"
        diff $old_fname $new_fname > $diff_fname
    done
}

for ip in ${switches[@]}; do
    is_reachable $ip
    if [[ $? -ne 0 ]]; then
        exit 1
    fi

    run_cli $1 "role-modify name $USER shell"
    run_cli $1 "role-modify name $USER sudo"
done

for (( cnt=0; cnt<=$REBOOT_CNT; cnt++ )); do
    FAIL=0
    for ip in ${switches[@]}; do
        is_reachable $ip
        if [[ $? -ne 0 ]]; then
            exit 1
        fi
        collect_logs $ip $cnt &
    done
    for job in `jobs -p`
    do
        wait $job || let "FAIL+=1"
    done
    if [ "$FAIL" -ne "0" ]; then
        echo "> Log collection failed !"
        exit 1
    fi
    if [[ $cnt -ne 0 ]]; then
	get_diff $cnt
    fi
    if [[ $cnt -ne $REBOOT_CNT ]]; then
        FAIL=0
	sleep 2
        for ip in ${switches[@]}; do
            reboot_sw $ip &
        done
        for job in `jobs -p`
        do
            wait $job || let "FAIL+=1"
        done
        if [ "$FAIL" -ne "0" ]; then
            echo "> Reboot failed !"
            exit 1
        fi
        sleep 5
    fi
done
