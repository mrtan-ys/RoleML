# The following content is copied from roleml/scripts/runner/recipes/resource/resource.sh
# Please keep this file consistent with the original file

if [ ! ${1} ]; then
    echo "A PID must be specified!"
    exit -1
fi
echo "====== Monitoring CPU and RAM usage ======"
echo "PID of process to monitor is ${1}; PID of current script is $$"
PID="${1}"
while true; do
    if [ ! -r "/proc/${PID}/status" ]; then
        echo "The process has exited or an error has occurred, monitoring done.";
        break;
    fi

    cpuUsage=$(ps -p "${PID}" -o %cpu= | awk '{print $1}') || {
        echo "Failed to collect CPU usage for PID ${PID}."
        break
    }
    memUsage=$(ps -p "${PID}" -o rss=,vsz= | awk '{print "RSS " $1 " KiB; VSZ " $2 " KiB"}') || {
        echo "Failed to collect memory usage for PID ${PID}."
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