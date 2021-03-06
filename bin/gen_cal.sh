#!/bin/bash
if [[ $# -lt 4 ]]
then
  echo "Usage: $0 <city name> <lat> <lon> <tz name> [year] [script]"
  exit 1
fi
if [[ $# -eq 6 ]]
then
  script=$6
  y=$5
elif [[ $# -eq 5 ]]
then
  y=$5
  script="devanagari"
elif [[ $# -gt 6 ]]
then
  echo "Usage: $0 <city name> <lat> <lon> <tz name> [year] [script]"
  exit 1
else
  y=`date +%Y`
  script="devanagari"
fi

city_name=$1
lat=$2
lon=$3
tz=$4
scr=${script:0:4}

echo -ne "Computing $y monthly panchangam for $city_name ($lat,$lon) - $tz in $script script... "
cd ../panchangam/
./write_monthly_panchangam_tex.py $city_name $lat $lon $tz $y $script > ../tex/data/cal-$y-$city_name-$scr.tex
if [[ $? -eq 0 ]]
then
  cd ../tex/data/
  echo "done. "
  echo -ne "Generating PDF (log --> /tmp/cal-$y-$city_name-$scr.texlog)... "
  xelatex -halt-on-error cal-$y-$city_name-$scr.tex > /tmp/cal-$y-$city_name-$scr.texlog
  echo done
else
  echo "error!"
fi
cd ../../panchangam/

echo -ne "Computing $y daily panchangam for $city_name ($lat,$lon) - $tz in $script script... "
./write_daily_panchangam_tex.py $city_name $lat $lon $tz $y $script > ../tex/data/daily-cal-$y-$city_name-$scr.tex
mv cal-*-log* debug_logs/
if [[ $? -eq 0 ]]
then
  cd ../tex/data/
  echo "done. "
  echo -ne "Generating PDF (log --> /tmp/cal-$y-$city_name-$scr.texlog)... "
  xelatex -halt-on-error daily-cal-$y-$city_name-$scr.tex > /tmp/cal-$y-$city_name-$scr.texlog
  echo done
  
  mv cal-$y-$city_name-$scr.pdf ../../pdf/
  mv daily-cal-$y-$city_name-$scr.pdf ../../pdf/
else
  echo "error!"
fi
