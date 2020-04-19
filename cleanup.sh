#!/bin/sh

ip=$(/sbin/ip addr | sed -nr 's|^.*inet (172.[^/]*)/.*$|\1|p')

sed -nr 's|^\[([0-9].*)\].*$|\1|p' /mnt/weka/026-detector_prelayout.job | xargs -ri mkdir -p /mnt/weka/${ip}/{}

for d in $(sed -nr 's|^\[([0-9].*)\].*$|\1|p' /mnt/weka/026-detector_prelayout.job); do
    find /mnt/weka -xdev -maxdepth 1 -type f -name "${ip}.${d}.*" | parallel -j 100 mv {} /mnt/weka/${ip}/${d}/
done
