if [ ! ${1} ]; then
    echo "A PID must be specified!"
    exit -1
fi

PID="${1}"
OS_NAME=$(uname -s)

echo "====== Monitoring CPU and RAM usage ======"
echo "PID of process to monitor is ${PID}; PID of current script is $$"

while true; do
    if ! kill -0 "${PID}" 2>/dev/null; then
        echo "The monitored process has exited or is no longer accessible, monitoring done."
        break
    fi

    case "${OS_NAME}" in
        Linux)
            cpuUsage=$(top -b -n 1 -p "${PID}" 2>/dev/null | awk -v pid="${PID}" '$1 == pid {print $9; exit}') || {
                echo "Failed to collect CPU usage on Linux."
                break
            }
            ;;
        Darwin)
            cpuUsage=$(top -l 1 -pid "${PID}" -stats pid,cpu 2>/dev/null | \
                awk -v pid="${PID}" '$1 == pid {gsub("%", "", $2); print $2; exit}') || {
                echo "Failed to collect CPU usage on macOS."
                break
            }
            ;;
        *)
            echo "Unsupported operating system for CPU monitoring: ${OS_NAME}."
            break
            ;;
    esac
    if [ -z "${cpuUsage}" ]; then
        echo "Failed to parse CPU usage on ${OS_NAME}."
        break
    fi
    memUsage=$(ps -p "${PID}" -o rss=,vsz= | awk 'NR==1 {print "RSS " $1 " KiB; VSZ " $2 " KiB"}') || {
        echo "Failed to collect memory usage."
        break
    }
    case "${OS_NAME}" in
        Linux)
            now=$(date --iso-8601=ns) || {
                echo "Failed to collect timestamp on Linux."
                break
            }
            ;;
        Darwin)
            now=$(date '+%Y-%m-%dT%H:%M:%S%z') || {
                echo "Failed to collect timestamp on macOS."
                break
            }
            ;;
    esac

    echo "${now} -- CPU: ${cpuUsage}%; RAM: ${memUsage}" || break
    sleep 0.5
done
