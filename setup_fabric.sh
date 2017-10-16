#!/bin/bash

FAIL=0

verizon_switches=(
        '10.9.31.60'
        '10.9.31.61'
        '10.9.31.62'
        '10.9.31.63'
        '10.9.31.64'
        '10.9.31.65'
        '10.9.31.66'
        '10.9.31.67'
        '10.9.31.68'
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

PS3='Which setup do you want to create fabric for? Please enter your choice: '
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
read -p "Are you sure you want to create fabric for $opt setup? [y|n] = " -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
	exit 0
fi

read -p "Duh... You must specify a name for your fabric = " -r
if [[ -z $REPLY ]]; then
	echo "Must specify something ! Exiting..!"
	exit 0
fi
fab_name=$REPLY

echo "==========================================="
echo "Please wait initialising switches"
echo "==========================================="

FIRST=0
for ip in ${switches[@]}; do
        sshpass -p admin ssh -q -oStrictHostKeyChecking=no pluribus@$ip -- --quiet cli --quiet --user network-admin:admin --no-login-prompt --script-password switch-setup-modify password test123 eula-accepted true
        if [[ $? -ne 0 ]]; then
                echo "Error accepting EULA"
                echo "Exiting.."
        fi
        sleep 2
        if [[ $FIRST -eq 0 ]]; then
                sshpass -p test123 ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet fabric-create name $fab_name fabric-network mgmt control-network mgmt
                sleep 5
        else
                sshpass -p test123 ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet fabric-join name $fab_name
        fi
        if [[ $? -ne 0 ]]; then
                echo "Error setting up fabric"
                echo "Exiting.."
        fi
        FIRST=1
done

echo "==========================================="
echo "All switches are successfully initialised :)"
echo "==========================================="
sshpass -p test123 ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet fabric-node-show format name,mgmt-ip,state
echo "==========================================="

exit 0
