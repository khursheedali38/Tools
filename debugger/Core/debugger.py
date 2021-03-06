#!/usr/bin/env python
import zmq
import sys
import time
import binascii
import argparse
import csv
#from scapy.utils import wrpcap

sys.path.insert(0,'../../../Engine/libraries/netip/python/')
sys.path.insert(0,'../../../ryu/ryu/')

from netip import *
from ofproto import ofproto_parser
from ofproto import ofproto_common
from ofproto import ofproto_protocol
from ofproto import ofproto_v1_0_parser
from ofproto import ofproto_v1_2_parser
from ofproto import ofproto_v1_3_parser
from ofproto import ofproto_v1_4_parser
from ofproto import ofproto_v1_5_parser


###################### headers for pcap creation ####################################

#Global header for pcap 2.4
pcap_global_header =   ('D4 C3 B2 A1'   
                        '02 00'         #File format major revision (i.e. pcap <2>.4)  
                        '04 00'         #File format minor revision (i.e. pcap 2.<4>)   
                        '00 00 00 00'     
                        '00 00 00 00'     
                        'FF FF 00 00'     
                        '93 00 00 00') #user_protocol selected, without Ip and tcp headers

#pcap packet header that must preface every packet
pcap_packet_header =   ('AA 77 9F 47'     
                        '90 A2 04 00'     
                        'XX XX XX XX'   #Frame Size (little endian) 
                        'YY YY YY YY')  #Frame Size (little endian)

#netide packet header that must preface every packet
netide_header =   ('01'                 #netide protocol version 1.1
                   '11'                 #openflow type
                   'XX XX'              #Frame Size (little endian) 
                   '01 00 00 00'        #xid 
                   '00 00 00 00 00 00 00 06') #datapath_id   

######################################################################################

###################### PCAP generation ########################################
def getByteLength(str1):
    return len(''.join(str1.split())) / 2
#    return len(str1)

def generatePCAP(message,i): 

    msg_len = getByteLength(message)
#    netide = netide_header.replace('XX XX',"%04x"%msg_len)
#    net_len = getByteLength(netide_header)
#    pcap_len = net_len + msg_len
    hex_str = "%08x"%msg_len
    reverse_hex_str = hex_str[6:] + hex_str[4:6] + hex_str[2:4] + hex_str[:2]
    pcaph = pcap_packet_header.replace('XX XX XX XX',reverse_hex_str)
    pcaph = pcaph.replace('YY YY YY YY',reverse_hex_str)

    if (i==0):
#        bytestring = pcap_global_header + pcaph + eth_header + ip + tcp + message
#        bytestring = pcap_global_header + pcaph + netide + message
        bytestring = pcap_global_header + pcaph + message
    else:
#        bytestring = pcaph + eth_header + ip + tcp + message
#        bytestring = pcaph + netide + message
        bytestring = pcaph + message
    return bytestring
#    writeByteStringToFile(bytestring, pcapfile)

#Splits the string into a list of tokens every n characters
def splitN(str1,n):
    return [str1[start:start+n] for start in range(0, len(str1), n)]

def sum_one(i):
    return i + 1

##############################################################################

parser = argparse.ArgumentParser(description='Launch the NetIDE debugger')
parser.add_argument('-o', help='Output Folder', default=".")

args = parser.parse_args()


fo = open(args.o+"/results.txt", "w")
bitout = open(args.o+"/results.pcap", 'wb')
csvfile = open(args.o+"/results.card", "w")
fieldnames = ['timestamp', 'origin', 'destination', 'msg', 'length']
#fieldnames = ['timestamp', 'origin', 'destination', 'msg']
writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
writer.writeheader()

# Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5557")
socket.setsockopt(zmq.SUBSCRIBE, "")
i = 0

print('[*] Waiting for logs. To exit press CTRL+C')
while True:
    dst_field, src_field, msg = socket.recv_multipart()
    t=time.strftime("%H:%M:%S")
    dst_field = str(dst_field)
    msg_str = str(msg)
    src_field = str(src_field)
    msg_hexadecimal = binascii.hexlify(msg)

    #print(src_field, dst_field)


    if src_field.startswith("0_", 0, 2) == True:
      origin = src_field[2:]
      destination = "core"

    elif src_field.startswith("1_", 0, 2) == True:
      origin = src_field[2:]
      destination = "core"

    elif src_field.startswith("2_", 0, 2) == True:
      origin = "core"
      destination = src_field[2:]

    elif src_field.startswith("3_", 0, 2) == True:
      origin = "core"
      destination = src_field[2:]


    #msg_cap = binascii.hexlify(msg)
    bytestring = generatePCAP(msg_hexadecimal,i)
    i = sum_one(i)
    bytelist = bytestring.split()
    bytes = binascii.a2b_hex(''.join(bytelist))
    bitout.write(bytes)
    

    
    (netide_version, netide_msg_type, netide_msg_len, netide_xid, netide_mod_id, netide_datapath) = NetIDEOps.netIDE_decode_header(msg)
    netide_msg_type_v2 = NetIDEOps.key_by_value(NetIDEOps.NetIDE_type, netide_msg_type)
    message_data = msg[NetIDEOps.NetIDE_Header_Size:]
    ret = bytearray(message_data)
    writer.writerow({'timestamp':t, 'origin':origin, 'destination':destination, 'msg':msg_hexadecimal, 'length':len(ret)})

    if len(ret) >= ofproto_common.OFP_HEADER_SIZE:
       (version, msg_type, msg_len, xid) = ofproto_parser.header(ret)
       msg_decoded = ofproto_parser.msg(netide_datapath, version, msg_type, msg_len, xid, ret)

    elif len(ret) < ofproto_common.OFP_HEADER_SIZE:
      (version, msg_type, msg_len, xid, msg_decoded) = ("", "", "", "", "")
    
    #if dst_field[2:] == "shim":
      #if 'msg_decoded' in locals() or 'msg_decoded' in globals():
    print "New message from %r to %r at %r"%(origin, destination, t)
    print "\033[1;32mNetIDE header: Version = %r, Type of msg = %r, Length = %r Bytes, XID = %r, Module ID = %r, Datapath = %r\033[1;m"% (netide_version, netide_msg_type_v2, netide_msg_len, netide_xid, netide_mod_id, netide_datapath)
    print '\033[1;32mOpenFlow message header: Version = %r, Type of msg = %r, Length = %r Bytes, XID = %r\033[1;m'% (version, msg_type, msg_len, xid)
    print '\033[1;32mOpenFlow message: %r \033[1;m'% (msg_decoded)
    print "\n"
      #writer.writerow({'timestamp':t, 'origin':dst_field, 'destination':src_field, 'msg':msg_hexadecimal, 'length':msg_len})
    fo.write("[%r] [%r] [%r] %r \n"% (t, origin, destination, msg_decoded))
    #else:
      #if 'msg_decoded' in locals() or 'msg_decoded' in globals():
      #print "New message from backend %r to %r at %r"%(dst_field, src_field, t)
      #print "\033[1;36mNetIDE header: Version = %r, Type of msg = %r, Length = %r Bytes, XID = %r, Module ID = %r, Datapath = %r\033[1;m"% (netide_version, netide_msg_type_v2, netide_msg_len, netide_xid, netide_mod_id, netide_datapath)
      #print '\033[1;36mOpenFlow message header: Version = %r, Type of msg = %r, Length = %r Bytes, XID = %r\033[1;m'% (version, msg_type, msg_len, xid)
      #print '\033[1;36mOpenFlow message: %r \033[1;m'% (msg_decoded)
      #print "\n"
      #writer.writerow({'timestamp':t, 'origin':dst_field, 'destination':src_field, 'msg':msg_hexadecimal, 'length':msg_len})
      #fo.write("[%r] [%r] %r \n"% (t, dst_field, msg_decoded))


fo.close()
bitout.close()
writer.close()