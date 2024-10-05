# The following content is copied from roleml/scripts/runner/recipes/temperature_rpi/temperature_rpi.sh
# Please keep this file consistent with the original file

echo "====== Probing RPI temperature ======"
echo "PID of current script is $$"
if [ ! ${1} ]; then
    duration=$((60*2))
else
    duration=$((${1}*2))
fi
count=0
while [ $count -lt $duration ]; do
    {
        temperature=$(vcgencmd measure_temp) &&
        now=$(date --iso-8601=ns) &&
        echo "${now} -- ${temperature}" &&
        let count+=1 &&
        sleep 0.5;
    } || {
        echo "An error has occurred, exiting.";
        exit -1;
    }
done
