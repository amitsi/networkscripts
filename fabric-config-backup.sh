#!/bin/bash

DEBUG=false
USER='root'
PASSWORD='test123'
SSHPASS=$( which sshpass )
ARCHIVE_LOGS=false
SHELL_TYPE=shell
SFTP_EXPORT='/nvOS/export/'
LOGDIR='/var/nvOS/log/'

usage() {
	cat <<_USAGE
usage: $0 [options] switch

  -u USER	user to SSH into the switch as
  -p PASS	password for user
  -s SSHPASS	path to sshpass command

  -S SFTPDIR	Path to SFTP export directory (default: $SFTP_EXPORT)

  -l		archive log files too

  -d		display debug messages
  -h		display this help message
_USAGE
}

die() {
	echo "ERROR: $*" >&2
	exit 2
}

debug() {
	"$DEBUG" || return
	echo "[DEBUG] $*" >&2
}

ssh_command() {
	$DEBUG && set -x
	"$SSHPASS" -p "$PASSWORD" ssh -q -o UserKnownHostsFile=/dev/null \
		-o StrictHostKeyChecking=no "${USER}@${SWITCHIP}" "$@"
	set +x
}

set_shell_type() {
	ssh_command software-show 2>/dev/null | grep '^version:' >/dev/null 2>&1
	[[ $? -eq 0 ]] && SHELL_TYPE=cli || SHELL_TYPE=shell
}

cli_command() {
	if [[ "$SHELL_TYPE" == 'cli' ]]; then
		ssh_command "$@" 2>&1 | grep -v '^Netvisor OS' | grep -v '^Connected to' \
			| grep -v 'time is not in sync with the NTP Server'
	else
		ssh_command cli -q "$@"
	fi
}

__scp_get() {
	"$SSHPASS" -p "$PASSWORD" scp -q -o UserKnownHostsFile=/dev/null \
		-o StrictHostKeyChecking=no "$@"
}

scp_get() {
	_file="$1"
	__scp_get "${USER}@${SWITCHIP}:${_file}" .
}

__sftp() {
	if $DEBUG; then
		"$SSHPASS" -p "$PASSWORD" sftp -o UserKnownHostsFile=/dev/null \
			-o StrictHostKeyChecking=no "$@"
	else
		"$SSHPASS" -p "$PASSWORD" sftp -o UserKnownHostsFile=/dev/null \
			-o StrictHostKeyChecking=no "$@" >/dev/null 2>&1
	fi
}

__mk_pack_dir_script() {
	_dir="$1"
	_packout="$2"
	_dirname=$( dirname $_dir )
	cat >"$TEMPSCRIPT" <<EOT
cd "$_dirname" || exit 1
echo "$PASSWORD" | sudo -S tar cf "$_packout" "$( basename $_dir )" 2>/dev/null
EOT
}

sftp_run_script() {
	_script="$1"
	_scriptname=$( basename $_script )

	__sftp "${USER}@${SWITCHIP}:${SFTP_EXPORT}" <<< $"put $_script"
	cli_command shell /bin/bash "${SFTP_EXPORT}/$_scriptname"
	__sftp "${USER}@${SWITCHIP}:${SFTP_EXPORT}" <<< $"rm $_scriptname"
}

sftp_rm() {
	_rmfile="$1"
	_rmfiledir=$( dirname $_rmfile )
	_rmfilepath=$( basename $_rmfile )
	__sftp "${USER}@${SWITCHIP}:$_rmfiledir" <<<$"rm $_rmfilepath"
}

__sftp_get_dir() {
	_arg="$1"
	_auth=${_arg%:*}
	_dir=${_arg#*:}
	_out="$( basename $_dir )-$( date +'%Y-%m-%d-%H%M%S' ).tar"
	__mk_pack_dir_script "$_dir" "${SFTP_EXPORT}/$_out"
	sftp_run_script "$TEMPSCRIPT"
	sftp_get "${SFTP_EXPORT}/$_out"
	sftp_rm "${SFTP_EXPORT}/$_out"
	tar xf "$_out"
	rm -f "$_out"
}

sftp_get() {
	_file="$1"
	if $DEBUG; then
		__sftp "${USER}@${SWITCHIP}:${_file}" .
	else
		__sftp "${USER}@${SWITCHIP}:${_file}" . >/dev/null 2>&1
	fi
}

get_file() {
	if [[ "$SHELL_TYPE" == 'cli' ]]; then
		sftp_get "$@"
	else
		scp_get "$@"
	fi
}

scp_get_dir() {
	_dir="$1"
	__scp_get -r "${USER}@${SWITCHIP}:${_dir}" .
}

sftp_get_dir() {
	_file="$1"
	__sftp_get_dir "${USER}@${SWITCHIP}:${_file}"
}

get_dir() {
	if [[ "$SHELL_TYPE" == 'cli' ]]; then
		sftp_get_dir "$@"
	else
		scp_get_dir "$@"
	fi
}

while getopts 'dhlp:s:S:u:' OPT; do
	case "$OPT" in
	d)	DEBUG=true ;;
	h)	usage; exit 0 ;;
	l)	ARCHIVE_LOGS=true ;;
	p)	PASSWORD="$OPTARG" ;;
	s)	SSHPASS="$OPTARG" ;;
	S)	SFTP_EXPORT="$OPTARG" ;;
	u)	USER="$OPTARG" ;;
	*)	exit 2 ;;
	esac
done
shift $(( OPTIND - 1 ))

SWITCH="$1"
CURRDIR="$PWD"

COMP1=${SWITCH%@*}
COMP2=${SWITCH#*@}
if [[ "$COMP1" != "$COMP2" ]]; then
	USER="$COMP1"
	SWITCH="$COMP2"
fi

SWITCHIP="$SWITCH"
if [[ -z "$SWITCH" ]]; then
	usage >&2
	exit 2
fi

[[ -x "$SSHPASS" ]] || die "sshpass command not found; use -s option"

set_shell_type

FABRIC_NAME=$( cli_command fabric-info format name layout horizontal \
	no-show-headers | tr -d ' 	' )
[[ -z "$FABRIC_NAME" ]] && die "Unable to determine fabric: $SWITCH"

echo "Fabric: $FABRIC_NAME"

FABRIC_SWITCHES=$( cli_command fabric-node-show format name,mgmt-ip parsable-delim : no-show-headers )
[[ -z "$FABRIC_SWITCHES" ]] && die "Unable to find fabric nodes of switch: $SWITCH"

NSWITCHES=$( echo "$FABRIC_SWITCHES" | wc -w | tr -d ' 	' )
echo "  $NSWITCHES switches in fabric"

TEMPDIR=$( mktemp -d )
cd "$TEMPDIR" || die "Failed to create temporary directory: $TEMPDIR"

TEMPSCRIPT=$( mktemp )
trap 'rm -rf "$TEMPDIR" "$TEMPSCRIPT"' EXIT

ARCHIVENAME="fabric-config.${FABRIC_NAME}.$( date +'%Y-%m-%d-%H%M' )"
ARCHIVEDIR="${TEMPDIR}/${ARCHIVENAME}"
mkdir "$ARCHIVEDIR"
cd "$ARCHIVEDIR" || die "Failed to create archive directory: $ARCHIVEDIR"

debug "Switches in fabric: $( echo "$FABRIC_SWITCHES" | tr -s '\n' ' ' )"
for SWITCHDET in $FABRIC_SWITCHES; do
	SWITCH=${SWITCHDET%:*}
	SWITCHIP=${SWITCHDET#*:}
	debug "Working with switch: $SWITCH ($SWITCHIP)"
	SWITCHDIR="${ARCHIVEDIR}/${SWITCH}"
	mkdir "$SWITCHDIR" || die "Failed to create directory: $SWITCHDIR"
	cd "$SWITCHDIR"

	set_shell_type

	VERSION=$( cli_command software-show format version layout horizontal \
		no-show-headers )
	[[ -z "$VERSION" ]] && die "Failed to determine nvOS version: $SWITCH"
	echo "$SWITCH ($SWITCHIP): version $VERSION"

	if [[ "$SHELL_TYPE" == 'cli' ]]; then
		for ACCESS in shell sudo; do
			echo "  $ACCESS access..."
			cli_command role-modify name "$USER" $ACCESS 
		done
	fi

	echo "  software-show..."
	cli_command software-show >software-show.txt

	echo "  running-config-show..."
	cli_command running-config-show >running-config-show.txt

	echo "  switch-config-export..."
	OUT=$( cli_command switch-config-export )
	EXPORT=$( echo "$OUT" | awk '{print $NF}' )
	[[ "$EXPORT" != /* ]] && die "Failed to export switch config: $OUT"

	get_file "$EXPORT"
	EXPORT_FILENAME=$( basename "$EXPORT" )
	[[ -f "$EXPORT_FILENAME" ]] \
		|| die "Failed to download config export: $EXPORT_FILENAME"

	$ARCHIVE_LOGS || continue

	echo "  log files..."
	get_dir "$LOGDIR"
done

echo "Bundling up the config backup"
cd "$TEMPDIR"
tar cf "${ARCHIVENAME}.tar" "$ARCHIVENAME"
bzip2 "${ARCHIVENAME}.tar"
OUTFILE="${ARCHIVENAME}.tar.bz2"
[[ -f "$OUTFILE" ]] || die "Failed to archive config backup"

if ! mv "$OUTFILE" "$CURRDIR"; then
	echo "ERROR: Failed to move config backup to current directory: $CURRDIR" >&2
	echo "Backup is here: ${TEMPDIR}/${OUTFILE}"
else
	echo "Backup created: $OUTFILE"
fi
