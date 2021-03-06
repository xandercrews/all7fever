#!/bin/sh

mountroot()
{
	cat <<EOF

,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,.S@#@@@#@@MH@#2;r;29rsAX2G#G,,,,,,,,,,,,,,,,,,,,,
                              ;@@@@B@@;  G@, i@B:@  @h ;@@s  ..................
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,.@@X:;, #A  @G, @@@@@i i& i@@@; ,::::::,,,::::::::
,,,TRINIDAD,,,,,,,,,,,,,,,,, s@@2 ss @@; #@: S@@#@G i@.,@@@M ,:::::::::::::::::
,,,,,JAMES,,,,,,,,,,,,,,,,,, M@@@: .;@@: r@@r ;Sr#G.:@; M@@@,.,::::::::::::::::
,,,,,,,,,,,,,,,,,,,,,,,,,,,. @@@@i 5,,#i9G@@@@##@@@@@@@AH@@@h .,,::,:::::::::::
,,,,,,,,,,,,,,,,,,,,,,,,,,,.:@@@@i;#@@@@@@@@@@@@@@@@@@@@@##@@r:,...,,::::::::::
,,,,,,,,,,,,,,,,,,,,,,,,,,, r@@@@@@@@@@@###@@@@@@@@@@@@@@@@@@@@&rr2:.,:::::::::
,,,,,,,,,,,,,,,,,,,,,,,,,,. ;@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@r ,::::::;;:
,,,,,,,,,,,,,,,,,,,,,,,:;,, ,@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@5.:::::;;;;
,,,,,,,,,,,,,,,,,,,,,,,,B@@@@@@@@@@@@@@@@@@B&3A@H325ir;;;;i@@@@@@@@@@r.::;;;;;;
,,,,,,,,,,,,,,,,,,,,,,:;@@@@@@@@@@@@@H3Sr;:  5s;r  ,,:;. .  9@@@@@@@@#r::;;;;;;
,,,,,,,,,,,,,,,,,::,:,:i@@@@@@@@@@#.  .,;rri. rs ;@A@@@@M@@  &@@@@@@@2;;;;;;;;;
,,,,,,,,,,:::::,,,,::,.,@@@@@@@@@#  @@@@@@#@@.;@.&@@@@@@@@@h @@@@@@@@;.:;;;;;;;
,,,,,,,,,,:::::::::::,. M@@@@@@@@; H@@@@@@@@@:s@A @@@@@@##@# @@@@@@@A:,;;;;;;rr
::::::::,::::::::::::,, :@@@@@@@@@ S@@@@@@@@@.MAAi.A@@@#MBMs @@@@@@A ,;;;;;;;r;
::::::,:::::::::::::::,.h@@@@@@@@@, @@#@@#@MrX&5s95::rsrr;;.G@##@@@5,;;;;;;;;rr
::::::::::::::::::::::,:#@@@@@@@@@@ ,S52ir;;&@@@#@@#X5523A#@@#B@@@2;;;;;;;;;;rr
::::::::::::::::::::::,:2A@@@@@@@@@#rriS5XGM@@@MMAM#Ahh&&AHA#@#@#G:;;;;;;;;rrrr
::::::::::::::::::::::,r53#@@@@@MM@@@@##MBAhhhh2239hh3X3G&AH@@##s::;;;;;;;;rrrr
::::::::::::::::::::::,;A5;s2A@@@M@@@BBHAG9GG&HBHHB#MHAA&&AM@#M9,,;;;;;;;;;rr;;
::::::::::::::::::::::,...   .@@@@@@@#HHAAB@#@@#M#BB#@@#HAAM@@A;,;;;:;;;;;;r;;;
:::::::::::::::::::::::,.,,,.,:h@@&@#MMMHH###BAXi559AHHBHHB##Gs:;;;:;;;;;;;r;;;
::::::::::::::::::::::::::;;;;,,;s2#@@#MBBBHBM#@@@@@#BHHBB@H: ,:;;:;;;;;;;;;;;;
:::::::::::::::::::::::;;;rrr;;:,:9s@@@@MBBBM#MM#BAAHHHHH#@A;,:;;::;;;;;;;;;;;;
:::::::::::::::::::::::;;rrrrrrrr,.i@@@@@#MBHBMMMHAAHMMM@@@HAXs;::;;;;;;;;;;;;;
:::::::::::::::::::::::;;rrrrrrrr  :@@@@@@@@@@@@###@@@@@@##9Xh3r;;;;;;;;;;;;;;;
::::::::::::::::::::::::;;rrrrrri,, 5@@##@@@@@@@@@@@@@@@M#&.:XX;r;.::;;;;;;;;;;
::::::::::::::::::::::::;;rrrssiir,  @@#MB#@@@@@@@@@@@#BH@A .iX;;.,::;;;;;;;;;;
:::::::::::::::::::::::;;rsssr;:.,:. &@@#BBM@@@@@@####MBM@@; r5; ,:;;;;;;;;;;;;
::::::::::::::::::;:;;;;;;;:.    ,::  @@@#MHB###MMMMMBBM#@@#;;i:,;;;;;;;;;;;;;;
:::::::::::::;;;;;;:::,,..    .....,, ;s3@#MBMMMMMMBHB###@A@@i;,;rr;;rr;;;;;;;;
::::::::::;::,,,,............,,,.... ;2;:G@#MMM###MHB##M#A2@@h.;;;:,,:;;rr;;;;;
::::::::::,......  .............. .. XA5r9@H&AHHHAAAHBHHBXM@S  ,.,... ..,::;;;;
:::::::;:   ....,......,..   ,.     ;@A92rH@MAGGh&AGA&AM&G@r  ...,,,,......,,:;
::::::;:,.......,........ ;&#@@#MM#XMHHH#: @@@@MA&GGAB@&MHr :;r,.,,,,,,,..,,,.,
EOF

	sleep 1
	configure_networking 
	sleep 1

    mount -t tmpfs tmpfs ${rootmnt}
	echo "extracting to ${rootmnt}"
	cd ${rootmnt}
	wget -O- ${ROOT} | gzip -dc | cpio -idmv 1>/dev/null 2>/dev/null
}
