serve:
	export ORTHANC_IP_ADDRESS=localhost; export DEBUG=1; export DATADIR=.; python scp.py

test:
	storescu -xf storescu.cfg Default -v localhost 104 in/*.dcm

install:
	cp nifscp.service /etc/systemd/system
	systemctl daemon-reload

restart:
	systemctl stop nifscp
	systemctl start nifscp

status:
	systemctl status nifscp

start:
	systemctl start nifscp

stop:
	systemctl stop nifscp
