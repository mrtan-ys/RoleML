# previous version
# if [ ! ${1} ]; then
#     echo "A PID must be specified!"
#     exit -1
# fi
# echo "====== Monitoring CPU and RAM usage ======"
# echo "PID of process to monitor is ${1}; PID of current script is $$"
# PID="${1}"
# while true; do
#     {
#         # TODO optimize this
#         cpuUsage=$(top -b -p ${1} -n 1 | grep ${1} | awk '{print $9}') &&
#         memUsage=$(awk '{ORS=" "} /VmSize|VmRSS/ {print $2,$3}' < /proc/${PID}/status) &&
#         now=$(date --iso-8601=ns) &&
#         echo "${now} -- CPU: ${cpuUsage}; RAM: ${memUsage}" &&
#         sleep 0.5;
#     } || {
#         echo "The process has exited or an error has occurred, monitoring done.";
#         break;
#     }
# done

# current version
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

    cpuUsage=$(ps -p "${PID}" -o %cpu= | awk '{print $1}') || break
    memUsage=$(ps -p "${PID}" -o rss=,vsz= | awk '{print $1 " KiB " $2 " KiB"}') || break
    now=$(date --iso-8601=ns) || break

    echo "${now} -- CPU: ${cpuUsage}%; RAM: RSS ${memUsage}" || break
    sleep 0.5
done
