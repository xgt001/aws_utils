set -x
export LC_ALL=C
sudo yum install perl-Switch perl-DateTime perl-Sys-Syslog perl-LWP-Protocol-https unzip perl-Digest-SHA.x86_64 aws-cli -y
curl http://aws-cloudwatch.s3.amazonaws.com/downloads/CloudWatchMonitoringScripts-1.2.1.zip -O
unzip CloudWatchMonitoringScripts-1.2.1.zip
rm CloudWatchMonitoringScripts-1.2.1.zip -f
mkdir -p /opt/monitoring/
mv aws-scripts-mon /opt/monitoring/
(crontab -l 2>/dev/null; echo "*/3 * * * * cd /opt/monitoring/aws-scripts-mon && ./mon-put-instance-data.pl --mem-util --mem-used-incl-cache-buff --mem-used --mem-avail --from-cron") | crontab -
(crontab -l 2>/dev/null; echo "*/5 * * * * cd /opt/monitoring/aws-scripts-mon && ./mon-put-instance-data.pl --disk-path=/ --disk-space-avail --disk-space-used --disk-space-util --from-cron") | crontab -

instance=$(curl http://169.254.169.254/latest/meta-data/instance-id)
name=$(curl http://169.254.169.254/latest/meta-data/hostname)

aws=$(which aws)

aws cloudwatch put-metric-alarm --alarm-name "$name Disk 70%" --alarm-description "$name Disk 70%" --metric-name DockerHostDiskSpaceUtilization --namespace System/Linux --statistic Average --period 300 --threshold 70 --comparison-operator GreaterThanThreshold --dimensions Name=Filesystem,Value=/dev/xvda1 Name=MountPath,Value=/ Name=InstanceId,Value=$instance --evaluation-periods 1 --actions-enabled --ok-actions $notify --alarm-actions $notify --unit Percent --region ap-southeast-1
