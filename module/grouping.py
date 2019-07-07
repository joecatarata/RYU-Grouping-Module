from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
import requests

#for adding meter {switch_id: executed: TRUE/FALSE}
switches = []
meter_settings = [{
                    "meter_id":1,
                    "rate":2000
                  },{
                    "meter_id":2,
                    "rate":3000
                  },{
                    "meter_id":3,
                    "rate":5000
                  }]

#per flow meter for device *edit to read a file
meter_groups = [{"mac":'b4:0f:b3:32:7d:3b', "group":"2"},
                {"mac":'04:d6:aa:98:94:ba', "group":"3"}]
#[{[src,dst],new:True}]
links = []


#clear flowmods variable after executing the config commands?
flowmods = []


class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)





    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        #print("sanity check")
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        #A device can be differentiated from other mac addresses if it is in port 2
        # add the default match meter(1) if it does not have a matching group


        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        #ignore MAC wan?
        #MAKE rest commands for flow mod later
        #execute after making flow
        for meter_group in meter_groups:
            #print(meter_group["mac"], "compare to", str(src))
            #[{[src,dst],new:True}]
            if str(src) == meter_group["mac"]:
                if not any(flowvar["flow"] == [src,dst] for flowvar in links) and dst != "ff:ff:ff:ff:ff:ff":
                    links.append({"flow":[src,dst], "new":True})
                    temp = '{"dpid":'+ str(dpid) +',"match":{"dl_dst":"'+ meter_group["mac"] +'"},"actions":[{"type":"OUTPUT","port": 2},{"type":"METER","meter_id":'+ meter_group["group"] +'}]}'
                    flowmods.append({"data":temp, "new":True})

        if in_port == 2 and not any(macvar["mac"] == str(src) for macvar in meter_groups):
            if not any(flowvar["flow"] == [src,dst] for flowvar in links) and dst != "ff:ff:ff:ff:ff:ff":
                links.append({"flow":[src,dst], "new":True})
                temp = '{"dpid":'+ str(dpid) +',"match":{"dl_dst":"'+ str(src) +'"},"actions":[{"type":"OUTPUT","port": 2},{"type":"METER","meter_id":1}]}'
                flowmods.append({"data":temp, "new":True})


        if not any(switch_var["switch_id"] == dpid for switch_var in switches): #CHECKING IF THE SWITCH IS ALREADY IN THE ARRAY
            switches.append({"switch_id": dpid, "is_done":False})
            #sanity check
            print(switches)

        # print("the switches checking if it adds")
        # print(switches)

        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)

        datapath.send_msg(out)

        self.add_meters()
        self.mod_flow()

    def mod_flow(self):
        # print("this is the flow mod")
        # print(flowmods)
        for flowmod in flowmods:
            if flowmod["new"]:
                response = requests.post('http://localhost:8080/stats/flowentry/modify', data=flowmod["data"])
                flowmod["new"] = False
                print("added mods")

    #ADDING METERS through ofctl rest
    def add_meters(self):
        data_array = []
        for switch in switches:
            if switch["is_done"] == False:
                for meter_setting in meter_settings:
                    datatemp = '{"dpid":' + str(switch["switch_id"]) +',"flags": "KBPS","meter_id": '+ str(meter_setting["meter_id"]) +',"bands": [{"type": "DROP","rate": '+ str(meter_setting["rate"]) +'}]}'
                    data_array.append(datatemp)
                    switch["is_done"] = True

        for data_inst in data_array:
            response = requests.post('http://localhost:8080/stats/meterentry/add', data=data_inst)

        #print("THIS IS THE data_array")
        #print(data_array)
