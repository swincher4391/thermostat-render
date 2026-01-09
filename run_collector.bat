@echo off
cd /d C:\dev\Budget\Atmos
python thermostat_collector.py >> thermostat.log 2>&1
