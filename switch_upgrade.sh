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

PS3='Which setup do you want to upgrade? Please enter your choice: '
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
read -p "Are you sure you want to upgrade $opt setup? [y|n] = " -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
	exit 0
fi

read -p "Enter the link to offline pkg = " -r
echo    # (optional) move to a new line
if [[ -z $REPLY ]]; then
	exit 0
fi
pkg_link=$REPLY

IFS='/ ' read -r -a array <<< "$pkg_link"
pkg_name="${array[-1]}"
if [[ -z $pkg_name ]]; then
	echo "Invalid offline pkg"
	exit 0
fi

echo "==========================================="
echo "Please wait upgrading all the switches..."
echo "==========================================="

for ip in ${switches[@]}; do
	echo "----------------------------------"
	echo "Switch : $ip"
	echo "----------------------------------"
        sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet role-modify name network-admin shell
        sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet role-modify name network-admin sudo
        echo "test123" | sshpass -p test123 ssh -oStrictHostKeyChecking=no network-admin@$ip "shell sudo -S -- sh -c 'mkdir -p /sftp/import; cd /sftp/import; rm *.pkg*'"
        echo "test123" | sshpass -p test123 ssh -oStrictHostKeyChecking=no network-admin@$ip "shell sudo -S -- sh -c 'wget $pkg_link -P /sftp/import'" &
done

for job in `jobs -p`
do
    wait $job || let "FAIL+=1"
done

echo "==========================================="
if [ "$FAIL" == "0" ]; then
        echo "Package was successfully downloaded on all the boxes"
else
        echo "Some issue downloading pkg. Please try manually !"
	exit 0
fi
echo "==========================================="


for ip in ${switches[@]}; do
	echo "----------------------------------"
	echo "Switch : $ip"
	echo "----------------------------------"
        sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet switch-setup-modify phone-home
        sshpass -p 'test123' ssh -q -oStrictHostKeyChecking=no network-admin@$ip -- --quiet software-upgrade package import/$pkg_name
done

echo "==========================================="
	echo "Done :)"
echo "==========================================="

exit 0

