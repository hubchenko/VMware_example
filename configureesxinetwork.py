#!/usr/bin/env python

""" Python script that allows updates a NIC config for a esxi host.
Module connects to a VC, checks the connection state, and attempts to re-register the VM in inventory.
Purpose of Module is to be put into a shinken monitor.

Credentials are pulled for fernet key/pair in private folder
"""
import argparse
import requests
import sys
import atexit
import json
import os

import vmware

from pyVim import connect
from pyVmomi import vim
from pyVmomi import vmodl

import paramiko
import time
import re
import ast



class ConfigureESXiNetwork():

    def __init__(self):
        parser = argparse.ArgumentParser(
            description='configure a standard switch for a esxi host')

        parser.add_argument(
            '--vc_fqdn',
            type=str,
            default='vsphere.vmware.com')

        parser.add_argument(
            '--vc_userid',
            type=str,
            default='vsphere_id')

        parser.add_argument(
            '--vc_passwd',
            type=str,
            default='vsphere_pass')

        parser.add_argument(
            '--hostname',
            type=str,
            default='myesxhostname.domain.com')

        parser.add_argument(
            '--esxi_user',
            type=str,
            default='root')

        parser.add_argument(
            '--esxi_password',
            type=str,
            default='root_pass')

        parser.add_argument(
            '--primary_nic',
            type=str,
            default='vmnic4')

        parser.add_argument(
            '--secondary_nic',
            type=str,
            default='vmnic5')

        parser.add_argument(
            '--networks',
            type=list,
            default={001:"v001_10-10-10-1_ShrdNet1", 002:"v002_10-10-10-2_ShrdNet2"})

        parser.add_argument(
            '--vswitch',
            type=str,
            default='vswith_prod')

        parser.add_argument(
            '--action',
            type=str,
            default='audit')

        args = parser.parse_args()

        self.vc_userid = args.vc_userid
        self.vc_passwd = args.vc_passwd
        self.vc_fqdn = args.vc_fqdn
        self.hostname = args.hostname
        self.action = args.action
        self.region = args.region
        self.vmnic_primary = args.primary_nic
        self.vmnic_secondary = args.secondary_nic
        self.name = "configureesxinetwork.py" 
        self.prod_extended_networks = args.networks
        self.vswitch_name = args.vswtich
        self.logfile_name = utils.get_logfile_name("update_barnics_esxi_" + self.region)
        self.log = open(os.path.join(self.logdir, self.logfile_name), "a")


        try:
            self.vc_connection = vmware.VMWare(vc_userid=self.vc_userid, vc_passwd= self.vc_passwd, vc_fqdn= self.vc_fqdn) # Create a vcenter connection
            message = "Successfully connected to {} as {}".format(self.vc_connection.vc_fqdn, self.vc_connection.vc_userid)
            print(message)

        except Exception as e:
            message = "Could not connect to vCenter in region and find the supplied host {}: {}".format(self.region, e)
            sys.exit()


    def collect_network_info(self):
        self.esxihost = self.vc_connection.get_host_by_name(self.hostname)
        self.host_network_system = self.esxihost.configManager.networkSystem
        self.uplinkset ="{},{}".format(self.vmnic_primary, self.vmnic_secondary)
        self.bond_name_primary = self.vc_connection.get_bridge_esxi_host(self.esxihost, self.vmnic_primary)
        self.bond_name_secondary = self.vc_connection.get_bridge_esxi_host(self.esxihost, self.vmnic_secondary)
        self.vmk_interface_primary= self.vc_connection.get_production_vmk_interface_esxi_host(self.esxihost, self.vmnic_primary)
        self.vmk_interface_secondary= self.vc_connection.get_production_vmk_interface_esxi_host(self.esxihost, self.vmnic_secondary)
        self.vmk_interface_primary_ip= self.vc_connection.get_vmk_interface_ip_esxi_host(self.esxihost, self.vmk_interface_primary)
        self.vmk_interface_secondary_ip= self.vc_connection.get_vmk_interface_ip_esxi_host(self.esxihost, self.vmk_interface_secondary)
        self.vmk_interface_primary_subnet= self.vc_connection.get_vmk_interface_subnet_esxi_host(self.esxihost, self.vmk_interface_primary)
        self.vmk_interface_secondary_subnet= self.vc_connection.get_vmk_interface_subnet_esxi_host(self.esxihost, self.vmk_interface_secondary)
        self.vswitches = self.vc_connection.get_vswitches(self.host_network_system)

    def get_current_profile(self):
        self.collect_network_info()
        profile = None
        self.vswitch_configured = False
        for vswitch in self.vswitches:
            if vswitch.name == self.vswitch_name:
                print "{} vswitch found".format(self.vswitch_name)
                self.vswitch_configured = True
                break
            else:
                print "migration switch not found"
        if (self.vmk_interface_primary and self.vmk_interface_secondary and not self.vswitch_configured):
            print "both intrerfaces are set in NSX, and no virtual vsphere switch detected.  Host fully managed by NSX"
            profile = 'sdn'
            return profile

        elif (self.vmk_interface_primary or self.vmk_interface_secondary and self.vswitch_configured):
            print " One of the vmnics is set in NSX, and a virtual vsphere switch detected. Split Network configuration"
            profile = 'split'
            return profile

        elif (not self.vmk_interface_primary and not self.vmk_interface_secondary and self.vswitch_configured):
            print " No vmnics are configrued for NSX, and a virtual vsphere switch is detected"
            profile = 'physical'
            return profile

        else:
            print "unable to determine state"
            return profile

    def create_vswitch(self, vmnicname):
        num_ports=128
        vswitch_name=self.vswitch_name
        hostname=self.hostname
        try:
            esxihost = self.vc_connection.get_host_by_name(hostname)
            host_network_system = esxihost.configManager.networkSystem
            self.vc_connection.create_vswitch(host_network_system, vswitch_name, num_ports, vmnicname)

            message = "found esxi host {} in the virtual center {} and configured switch".format(esxihost, self.vc_connection.vc_fqdn)
            print(message)

        except Exception as e:
            message = "Unable to configure vswtich on host {}: {}".format(hostname, e)
            utils.log_message(message, self.log, "ERROR")

    def delete_vswitch(self):
        vswitch_name=self.vswitch_name
        hostname=self.hostname
        try:
            esxihost = self.vc_connection.get_host_by_name(hostname)
            host_network_system = esxihost.configManager.networkSystem
            self.vc_connection.delete_vswitch(host_network_system, vswitch_name)

            message = "found esxi host {} in the virtual center {} and removed switch".format(esxihost, self.vc_connection.vc_fqdn)
            print(message)

        except Exception as e:
            message = "Unable to remove vswtich on host {}: {}".format(hostname, e)
            utils.log_message(message, self.log, "ERROR")


    def assign_prod_portgroups(self):
    	vswitch_name=self.vswitch_name
        if self.vswitch_configured:
            for key in self.prod_extended_networks:
                vlanid = key
                pg_name = self.prod_extended_networks[key]
                try:
                    self.vc_connection.create_port_group(self.host_network_system, pg_name, vlanid, vswitch_name)
                    message = "added vlanid {} with port group label {}".format(vlanid, pg_name)
                    print(message)
                except Exception as e:
                    message = "Unable to add vlan {}: {}".format(vlanid, e)
                    utils.log_message(message, self.log, "ERROR")
        else:
            message = "Unable to find vswitch {}, check virtual center. Error thown: {}".format(vswitch_name, e)
            utils.log_message(message, self.log, "ERROR")


    
    def run(self):
        utils.log_message("checking host {} in virtual center {}".format(self.hostname, self.vc_connection.vc_fqdn), self.log)
        if self.action == 'audit':
            message = "auditing host {} for a network profile".format(self.hostname)
            print(message)
            print "{}\n".format(message)
            profile_state = self.get_current_profile()
            message = "audit complete on host {}, currently configured as '{}'".format(self.hostname, profile_state)
            print(message)
            print "{}\n".format(message)

        elif self.action == 'update':
            message = "auditing host {} for a network profile".format(self.hostname)
            print(message)
            print "{}\n".format(message)
            profile_state = self.get_current_profile()
            message = "audit complete on host {}, currently configured as '{}'".format(self.hostname, profile_state)
            print(message)
            print "{}\n".format(message)
            message = "breaking the bond if exists "
            print(message)
            print "{}\n".format(message)
            if self.bond_name_primary:
                self.vc_connection.destroy_bond_esxi_host(self.esxihost, self.bond_name_primary)
            if self.bond_name_secondary and self.bond_name_primary != self.bond_name_secondary:
                self.vc_connection.destroy_bond_esxi_host(self.esxihost, self.bond_name_secondary)
            if self.vswitch_configured:
                message = "deleting vswitch from vsphere"
                print(message)
                print "{}\n".format(message)
                self.delete_vswitch()

            message = "setting vsphere switch"
            print(message)
            print "{}\n".format(message)

            niclist = list()
            niclist.append(self.vmnic_primary)
            niclist.append(self.vmnic_secondary)
            self.create_vswitch(niclist)
            message = "adding networks to vswitch"
            print(message)
            print "{}\n".format(message)
            self.assign_prod_portgroups()
            message = "checking state"
            print(message)
            print "{}\n".format(message)
            profile_state = self.get_current_profile()
            if profile_state == 'physical':
                message = "config completed without issue"
                print(message)
                print "{}\n".format(message)
                return True
            else:
                message = "State Does not match"
                print(message)
                print "{}\n".format(message)
                return False
        else:
            message = "Please use 'update' or 'audit' for the action type type, action submitted: {} network profile".format(self.action)
            print(message)
            print "{}\n".format(message)

def main():
    try:
        hostconfig = ConfigureESXiNetwork()
        hostconfig.run()

    except Exception as e:
        print("UNKNOWN - An exception has occured: {}".format(e))

if __name__ == '__main__':
    main()