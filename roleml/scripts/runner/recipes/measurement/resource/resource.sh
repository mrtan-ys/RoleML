#!/usr/bin/env sh
cleanup() {
    echo "The process has exited or an error has occurred, monitoring done."
    sleep 0.1
}

trap cleanup EXIT TERM INT HUP


if [ ! "${1}" ]; then
    echo "A PID must be specified!"
    exit -1
fi
echo "====== Monitoring CPU and RAM usage ======"
echo "PID of process to monitor is ${PID}; PID of current script is $$"
PID="${1}"
while true; do

    cpuUsage=$(top -b -n 1 -p "${PID}" 2>/dev/null | awk -v pid="${PID}" '$1 == pid {print $9; exit}') || {
        echo "Failed to collect CPU usage."
        break
    }

    memUsage=$(ps -p "${PID}" -o rss= -o vsz= | awk 'NR==1 {print "RSS " $1 " KiB; VSZ " $2 " KiB"}') || {
        echo "Failed to collect memory usage."
        break
    }

    now=$(date --iso-8601=ns) || {
        echo "Failed to collect timestamp."
        break
    }

    echo "${now} -- CPU: ${cpuUsage}%; RAM: ${memUsage}" || {
        echo "Failed to write resource usage log entry."
        break
    }
    sleep 0.5
done