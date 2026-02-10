set sqlformat csv
set feedback off
set termout off
spool d:\tools\dify\docker\pyfiles\alarms.csv
SELECT
    trim(telename) as telename,
    devicetype,
    alarmtype,
    alarmlevel,
    maintanceflag,
    alarmdes,
    createtime
FROM ALARM;
spool off
exit
