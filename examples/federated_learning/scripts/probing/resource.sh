# The following content is copied from roleml/scripts/runner/recipes/resource/resource.sh
# Please keep this file consistent with the original file

#!/usr/bin/env sh
if [ ! "${1}" ]; then
    echo "A PID must be specified!"
    exit -1
fi

cleanup() {
    echo "The process has exited or an error has occurred, monitoring done."
    sleep 0.1
}

trap cleanup EXIT TERM INT HUP

PID="${1}"
echo "====== Monitoring CPU and RAM usage ======"
echo "PID of process to monitor is ${PID}; PID of current script is $$"

while true; do
    cpuUsage=$(top -b -n 1 -p "${PID}" 2>/dev/null | awk -v pid="${PID}" '$1 == pid {print $9; exit}') || {
        echo "Failed to collect CPU usage."
        break
    }

    memUsage=$(awk '/VmSize|VmRSS/ {printf "%s %s KiB%s", $1=="VmRSS:"?"RSS":"VSZ", $2, ++n==1?", ":""}' < /proc/${PID}/status) || {
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