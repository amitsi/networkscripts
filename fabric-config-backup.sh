#!/bin/bash

DEBUG=false
USER='root'
PASSWORD='test123'
SSHPASS=$( which sshpass )
ARCHIVE_LOGS=false

usage() {
	cat <<_USAGE
usage: $0 [options] switch

  -u USER	user to SSH into the switch as
  -p PASS	password for user
  -s SSHPASS	path to sshpass command

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

cli_command() {
	ssh_command cli -q "$@"
}

__scp_get() {
	"$SSHPASS" -p "$PASSWORD" scp -q -o UserKnownHostsFile=/dev/null \
		-o StrictHostKeyChecking=no "$@"
}

scp_get() {
	_file="$1"
	__scp_get "${USER}@${SWITCHIP}:${_file}" .
}

scp_get_dir() {
	_dir="$1"
	__scp_get -r "${USER}@${SWITCHIP}:${_dir}" .
}

while getopts 'dhlp:u:' OPT; do
	case "$OPT" in
	d)	DEBUG=true ;;
	h)	usage; exit 0 ;;
	l)	ARCHIVE_LOGS=true ;;
	p)	PASSWORD="$OPTARG" ;;
	u)	USER="$OPTARG" ;;
	*)	exit 2 ;;
	esac
done
shift $(( OPTIND - 1 ))

SWITCH="$1"
CURRDIR="$PWD"

SWITCHIP="$SWITCH"

[[ -x "$SSHPASS" ]] || die "sshpass command not found; use -s option"

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
trap 'rm -rf "$TEMPDIR"' EXIT

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

	VERSION=$( cli_command software-show format version layout horizontal \
		no-show-headers )
	[[ -z "$VERSION" ]] && die "Failed to determine nvOS version: $SWITCH"
	echo "$SWITCH: version $VERSION"

	echo "  software-show..."
	cli_command software-show >software-show.txt

	echo "  running-config-show..."
	cli_command running-config-show >running-config-show.txt

	echo "  switch-config-export..."
	OUT=$( cli_command switch-config-export )
	EXPORT=$( echo "$OUT" | awk '{print $NF}' )
	[[ "$EXPORT" != /* ]] && die "Failed to export switch config: $OUT"

	scp_get "$EXPORT"
	EXPORT_FILENAME=$( basename "$EXPORT" )
	[[ -f "$EXPORT_FILENAME" ]] \
		|| die "Failed to download config export: $EXPORT_FILENAME"

	$ARCHIVE_LOGS || continue

	echo "  log files..."
	scp_get_dir "/var/nvOS/log"
done

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
