import requests
import json
import time
import datetime
import sys
import re

currentDT = datetime.datetime.now()

#switch_ip ="10.9.0.121"
switch_ip ="10.36.10.45"

auth = requests.auth.HTTPBasicAuth('network-admin', 'test123')
def main():
	print(sys.argv[1])
	if sys.argv[1] == "vport":
		print("Show vPort for the last 18 hours DEMO")
		vport()
	elif sys.argv[1] == "static_route":
		print ("Creating a static route DEMO")
		static_route()
	elif sys.argv[1] == "ospf_cost":
		print("Changing OSPF Cost Demo")
		ospf_cost()
	elif sys.argv[1] == "fabjoin":
		print("Rejoining a existing fabric/RMA'd Leaf3")
		fabjoin()

#vrouter-interface-config-modify vrouter-name spine2-vrouter nic eth8.4091 ospf-cost 10
#vrouter-static-route-remove vrouter-name spine2-vrouter network 1.2.3.0/24

def vport():
	cur_time = ("%d-%d-%dT%d:%d:%d" %(currentDT.year, currentDT.month, currentDT.day, currentDT.hour , currentDT.minute , currentDT.second))
	print(cur_time)
	auth = requests.auth.httpbasicauth('network-admin', 'test123')
	r = requests.get(('http://%s:80/vRest/vports?last-seen-since=%s' % (switch_ip, cur_time)), auth=auth)
	print(str(r))
	print(json.dumps(r.json(), indent =4))
	print("*"*100)
	print("Since : %s" %cur_time )
	print("*"*100)
	time.sleep(10)

def ospf_cost():
	print("Printing Interface Configuration, look at ospf-cost of 10")
	r = requests.get('http://%s:80/vRest/vrouters/spine2-vrouter/interface-configs' %switch_ip, auth=auth)
	print(json.dumps(r.json(), indent =4))

	time.sleep(10)
	print("*"*100)
	data_ospf_cost = {"ospf-cost" :  100}
	print("Configuring ospf-cost of 100")
	data_static_route = {"network": "1.2.3.4","netmask" :24 , "gateway-ip": "1.2.3.1"}
	url = ("http://%s:80/vRest/vrouters/spine2-vrouter/interface-configs/eth8.4091" %switch_ip)
	data_json = json.dumps(data_ospf_cost)
	r2 = requests.put(url, data=data_json, auth=auth)
	#print(r2.json())
	print(json.dumps(r2.json(), indent =4))
	print("Configured OSPF Cost")
	print("*"*100)
	print("Printing Interface Configuration, look at ospf-cost of 10")
	r = requests.get('http://%s/vRest/vrouters/spine2-vrouter/interface-configs' %switch_ip, auth=auth)
	print(json.dumps(r.json(), indent =4))

def static_route():
	print("*"*100)
	print("Printing Static Routes Show")
	r = requests.get('http://%s/vRest/vrouters/spine2-vrouter/static-routes' %switch_ip, auth=auth)
	print(json.dumps(r.json(), indent =4))

	print("*"*100)
	time.sleep(10)
	print("Configuring Static Routes Show")
	url = ("http://%s:80/vRest/vrouters/spine2-vrouter/static-routes" %switch_ip)
	data_json = json.dumps(data_static_route)
	headers = {'Content-type': 'application/json'}
	response = requests.post(url, data=data_json, auth=auth)
	print(json.dumps(response.json(), indent=4))

	print("*"*100)
	time.sleep(10)
	print("Display Configured Static Routes Show")
	r = requests.get('http://%s/vRest/vrouters/spine2-vrouter/static-routes' %switch_ip, auth=auth)
	print(json.dumps(r.json(), indent =4))

	print("*"*100)

def fabjoin():
	print("Show Fabric")
	url = "http://10.9.0.105:80/vRest/fabrics"
	headers = {'Content-type': 'application/json'}
	response = requests.get(url, auth=auth)
	print(json.dumps(response.json(), indent=4))

	url = "http://10.9.0.105:80/vRest/fabric-nodes"
	headers = {'Content-type': 'application/json'}
	response = requests.get(url, auth=auth)
	out = json.dumps(response.json(), indent=4)
	for line in out:
    		if re.search("name", line):
        		print line,
        		if line == None:
            			print 'no matches found'

	print(json.dumps(response.json(), indent=4))
	print("*"*100)
	time.sleep(10)
	print("RePeer/Rejoin Cluster Node")
	r = requests.post("http://10.9.0.107:80/vRest/fabrics/join",auth=('network-admin','test123'), data=json.dumps({'repeer-to-cluster-node': 184551696}))
#	r = requests.get('http://10.9.0.105:80/vRest/vrouters/spine2-vrouter/static-routes' %switch_ip, auth=auth)
	print(json.dumps(r.json(), indent =4))



main()
