import utils
import atexit
import paramiko
import time
import re

from pyVim import connect
from pyVmomi import vim
from pyVmomi import vmodl
from requests.auth import HTTPBasicAuth



class VMWare:
    """Connects to VMware Virtual Center to provide a number of queries and methods to administor Virtual Center programtically
    This Class leverages the pyvmomi library pretty extensivly: https://github.com/vmware/pyvmomi
    Args:
        vc_userid:  = 'myVMwareAdminId'
        vc_passwd:  = 'myVMwareAdminpassword'
        vc_fqdn:    ='myVsphereFQDN'
        esxi_user:  ='myEsxiAdminId'
        esxi_password: ='myEsxiAdminpass'

    Example:
        As Script:
            Not Applicable
        As Reference
                y = vmware.VMWare(vc_userid = 'myVMwareAdminId', vc_passwd = 'myVMwareAdminpassword', vc_fqdn ='myVsphereFQDN', esxi_user='myEsxiAdminId', esxi_password='myEsxiAdminpass',)
                    Defines Instance
                esxihost = y.get_host_by_name('myesxhost.fqdn.domain.com')
                	returns host VIM object for model for a given host
                host_network_system = esxihost.configManager.networkSystem
                	abstracts network system for host, to be used for network config
                vmnic = y.get_vmnic_esxi_host(esxihost, 'maccaddress')
                    returns vmknic specified by MAC
                bond_name = y.get_bridge_esxi_host(esxihost, 'vmnic3')
                    get bridge/bond for nix
                vmk_interface= y.get_production_vmk_interface_esxi_host(esxihost, 'vmnic3')
                    get VMK interface for vmnic
                vmk_ip = y.get_vmk_interface_ip_esxi_host(esxihost, 'vmk1')
                	get IP of a VMK interface
                vmk_subnet = y.get_vmk_interface_subnet_esxi_host(esxihost, 'vmk1')
                	get subnet of VMK interface
                nsx_gateway_ip = y.get_nsx_gateway_esxi_host(esxihost, 'tunneling')
                    returns active gateway 
                switches = y.get_vswitches(host_network_system)
    Methods:
        create_bond_esxi_host(esxihost,bond_name,uplinks): create NSX bond.
        set_interface_uplink_esxi_host(esxihost, bond_name, vmk_ip, vmk_subnet): configues NSX.
        connect_uplink_esxi_host(esxihost, bond_name)
        destroy_bond_esxi_host(esxihost,bond_name): destroy NSX bond
        test_nsx_gateway_esxi_host(esxihost, 'vmk1', '10.10.10.1'): pings NSX gateay from host
    """

    def __init__(self, vc_userid, vc_passwd, vc_fqdn, esxi_user, esxi_password):

        self.vc_userid = vc_userid
        self.vc_passwd = vc_passwd
        self.vc_fqdn = vc_connection
        self.vc_connection = self._get_vcenter_connection()
        self.vm_names = {}
        self.virtual_machines = []
        self.esxi_credentials = {"user": esxi_user,
                                "passwd": esxi_password}
        self.esxi_hosts = []
        self.ha_clusters = [] 
        self._init_esxi_hosts()


    def _get_vcenter_connection(self):
        service_instance = None
        print "INFO: Connecting to vCenter {} as {}".format(self.vc_fqdn, self.vc_userid)
        try:
            service_instance = connect.SmartConnect(host=self.vc_fqdn,
                                                    user=self.vc_userid,
                                                    pwd=self.vc_passwd)
            atexit.register(connect.Disconnect, service_instance)
        except IOError as ex:
            raise Exception("Unable to connect to the vCenter with with supplied credentials. {}".format(ex))
        print "INFO: vCenter connection successful"
        return service_instance

    def _get_container_view(self, view_type):
        content = self.vc_connection.RetrieveContent()
        container = content.rootFolder
        recursive = True
        container_view = content.viewManager.CreateContainerView(container, view_type, recursive)
        return container_view

    def _get_container(self):
        content = self.vc_connection.RetrieveContent()
        dc_container = content.rootFolder
        return dc_container

    def _get_all_objs(self, content, vimtype):
        """
        Get all the vsphere objects associated with a given type
        """
        obj = {}
        container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
        for c in container.view:
            obj.update({c: c.name})
        return obj

    def _get_obj(self, content, vimtype, name):
        """
        Get the vsphere object associated with a given text name
        """
        obj = None
        container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
        for c in container.view:
            if c.name == name:
                obj = c
                break
        return obj

    def get_ssh_connection(host, user, passwd, vmware=False):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=passwd)
        return ssh

    def get_hosts_on_ha_cluster(self, ha_cluster_name):
        ha_hosts = []
        for cluster in self.ha_clusters:
            if cluster.name == ha_cluster_name:
                ha_hosts = cluster.host
                host_names = [host.name for host in ha_hosts]
        return ha_hosts

    def get_hosts(self):
        """
        Returns all hosts
        """
        return self._get_all_objs(self.vc_connection.RetrieveContent(), [vim.HostSystem])


    def get_host_service(self, host, svc_key):
        # EX: 'TSM-SSH' for SSH
        services = host.configManager.serviceSystem.serviceInfo.service
        srvc = [service for service in services if service.key == svc_key][0]
        return srvc

    def toggle_host_service(self, host, service, state):
        serviceManager = host.configManager.serviceSystem
        if state == 'on':
            if not service.running:
                serviceManager.StartService(id=service.key)
        if state == 'off':
            if service.running:
                serviceManager.StopService(id=service.key)


    def get_host_by_name(self, name):
        """
        Find a virtual machine by it's name and return it
        """
        return self._get_obj(self.vc_connection.RetrieveContent(), [vim.HostSystem], name)

    def _init_esxi_hosts(self):
       print "INFO: Initializing ESXI hosts"
       vimtype = [vim.HostSystem]
       self.esxi_hosts = (self._get_container_view(vimtype)).view
       print "INFO: Completed ESXI Host init"


  
    def get_esxi_host(self, esx_hostname):
        content = self.vc_connection.RetrieveContent()
        esxi_host = content.searchIndex.FindByDnsName(None, esx_hostname, vmSearch=False)
        return esxi_host




    def get_vswitches(self, host_network_system):
        vswitches = host_network_system.networkConfig.vswitch
        if vswitches:
        	for key in vswitches:
        		print "Found vswtich '{}' on host".format(key.name)
        	return vswitches
    	else:
    		print "no vswitches found"
    		return None


        host_network_system.AddVirtualSwitch(vswitchName=vss_name, spec=vss_spec)

        print "Successfully created vSwitch ",  vss_name

    def delete_vswitch(self, host_network_system, vswitchName):
        host_network_system.RemoveVirtualSwitch(vswitchName=vswitchName)
        print "Successfully Deleted vSwitch ",  vswitchName

    def create_vswitch(self, host_network_system, vss_name, num_ports, nic_name):
        vss_spec = vim.host.VirtualSwitch.Specification()
        vss_spec.numPorts = num_ports
        vss_spec.bridge = vim.host.VirtualSwitch.BondBridge(nicDevice=nic_name)
        host_network_system.AddVirtualSwitch(vswitchName=vss_name, spec=vss_spec)

        print "Successfully created vSwitch ",  vss_name


    def create_port_group(self, host_network_system, pg_name, vlanId, vswitchName):
        port_group_spec = vim.host.PortGroup.Specification()
        port_group_spec.name = pg_name
        port_group_spec.vlanId = vlanId
        port_group_spec.vswitchName = vswitchName

        security_policy = vim.host.NetworkPolicy.SecurityPolicy()
        security_policy.allowPromiscuous = False
        security_policy.forgedTransmits = True
        security_policy.macChanges = True

        port_group_spec.policy = vim.host.NetworkPolicy(security=security_policy)

        host_network_system.AddPortGroup(portgrp=port_group_spec)

        print "Successfully created PortGroup ",  pg_name

    def delete_port_group(self, host_network_system, pg_name):
        host_network_system.RemovePortGroup(pgName=pg_name)
        print "Successfully deleted PortGroup ",  pg_name


    def add_virtual_nic(host_network_system, pg_name):
        vnic_spec = vim.host.VirtualNic.Specification()
        vnic_spec.ip = vim.host.IpConfig(dhcp=True)
        host_network_system.AddServiceConsoleVirtualNic(portgroup=pg_name, nic=vnic_spec)


    def get_vmnic_esxi_host(self, esx_host, mac_address):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "esxcli network nic list | grep {} | head -c6".format(mac_address)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format("\n".join(stderr_data))
            return None
        vmnic = stdout.read()
        ssh.close()
        if vmnic:
        	print "the vmnic '{}' is assoicated with the mac address '{}' provided".format(vmnic, mac_address)
        else:
        	print "no vmnic found for mac address:'{}'".format(mac_address)
        return vmnic

    def get_bridge_esxi_host(self, esx_host, vmnic):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "nsx-dbctl show | grep -i \'interface \"{}\"\' -B 2 | grep -i port | sed -e \'s/Port \"\\(.*\\)\"/\\1/\'".format(vmnic)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return None
        bridge = stdout.read().strip()
        ssh.close()
        if bridge:
        	print "the vmnic '{}' has the bridge {} associated with it".format(vmnic, bridge)
        else:
        	print "no bridge found for vmnic '{}'".format(vmnic)
        return bridge

    def get_production_vmk_interface_esxi_host(self, esx_host, vmnic):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "nsx-dbctl show | grep -i \'interface \"{}\"\' -A 4 -B 4 | grep -i vmk | grep -i port | sed -e \'s/Port \"\\(.*\\)\"/\\1/\'".format(vmnic)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return None
        vmkname  = stdout.read().strip()
        if vmkname:
        	print "the interface for vmnic '{}' is '{}'".format(vmnic, vmkname)
        else:
        	print "no vmkinterface found for vmnic '{}'".format(vmnic)
        ssh.close()
        return vmkname

    def get_vmk_interface_ip_esxi_host(self, esx_host, vmk_interface):
    	if vmk_interface:
	        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
	        command = "nsxcli uplink/show | grep -A 5 {}  | grep IP | sed -e \'s/IP        : \\([0-9]\\{{1,3\\}}\\.[0-9]\\{{1,3\}}\\.[0-9]\\{{1,3\\}}\.[0-9]\\{{1,3\\}}\\).*/\\1/\'".format(vmk_interface)
	        stdin, stdout, stderr = ssh.exec_command(command)
	        stderr_data = stderr.read()
	        if len(stderr_data) > 0:
	            ssh.close()
	            print "ERROR: {}".format(stderr_data)
	            return None
	        vmkip = stdout.read().strip()
	        ssh.close()
	        if vmkip:
	        	print "the ip for '{}' is '{}'".format(vmk_interface, vmkip)
	        else:
	        	print "no ip for NSX found for interface '{}'".format(vmk_interface)     	
	        return vmkip
        else:
        	print "no vmk interface; unable to provide ip"
	    	return None

    def get_vmk_interface_subnet_esxi_host(self, esx_host, vmk_interface):
    	if vmk_interface:
	        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
	        command = "nsxcli uplink/show | grep -A 5 {}  | grep Mask | sed 's/Mask      : \\([0-9]\\{{1,3\\}}\\.[0-9]\\{{1,3\}}\\.[0-9]\\{{1,3\\}}\.[0-9]\\{{1,3\\}}\\).*/\\1/\'".format(vmk_interface)
	        stdin, stdout, stderr = ssh.exec_command(command)
	        stderr_data = stderr.read()
	        if len(stderr_data) > 0:
	            ssh.close()
	            print "ERROR: {}".format(stderr_data)
	            return None
	        vmksubnet = stdout.read().strip()
	        ssh.close()
	        if vmksubnet:
	        	print "the subnet for '{}' is '{}'".format(vmk_interface, vmksubnet)
	        else:
	         	print "no subnet for NSX found for interface '{}'".format(vmk_interface)            	
	        return vmksubnet
        else:
        	print "no vmk interface; unable to provide subnet"
	    	return None

    def get_nsx_gateway_esxi_host(self, esx_host, gateway_type):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "nsxcli gw/show | grep -i {} -A 2  | grep -i \'currently active default gateway\' | sed 's/Currently active default gateway : \\([0-9]\\{{1,3\\}}\\.[0-9]\\{{1,3\}}\\.[0-9]\\{{1,3\\}}\.[0-9]\\{{1,3\\}}\\).*/\\1/\'".format(gateway_type)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return None
        nsxgateway = stdout.read().strip()
        ssh.close()
        if nsxgateway:
        	print "NSX gatway returned as '{}'".format(nsxgateway)
        else:
         	print "no NSXgateway found for esxi host '{}'".format(esx_host.name)          
        return nsxgateway

    def test_nsx_gateway_esxi_host(self, esx_host, interface, gateway_ip):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "vmkping ++netstack=nsxTcpipStack -I {} {}".format(interface, gateway_ip)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return False
        response = stdout.read()
        ssh.close()
        if "0% packet loss" in response:
        	print "ping from interface {} to gateway {} is successfull, connectivity looks good".format(interface, gateway_ip)
        	return True
        else:
        	print "unable to ping from interface {} to gateway {}; getting packet loss. response string attached: {} connectivity looks good".format(interface, gateway_ip, response)
        	return False



    def destroy_bond_esxi_host(self, esx_host, bond):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "nsxcli bond/destroy {}".format(bond)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return False
        ssh.close()
        print "the bond '{}' was destroyed on the ESXi host '{}'".format(bond, esx_host.name)
        return True


    def create_bond_esxi_host(self, esx_host, bond, uplinks):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "nsxcli bond/create {}  uplink={}".format(bond, uplinks)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return False
        ssh.close()
        print "the bond '{}' was created on the ESXi host '{}' with the following uplinks: '{}'".format(bond, esx_host.name, uplinks)
        return True


    def set_interface_uplink_esxi_host(self, esx_host, interface, vmht_ip, vmht_subnet):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "nsxcli uplink/set-ip {} {} {}".format(interface, vmht_ip, vmht_subnet)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return False
        ssh.close()
        print "for the interface '{}' on the ESXi host '{}',  setting the VMHT IP to '{}' and subnet '{}'".format(interface, esx_host.name, vmht_ip, vmht_subnet)       
        return True

    def connect_uplink_esxi_host(self, esx_host, interface):
        ssh = utils.get_ssh_connection(esx_host.name, self.esxi_credentials['user'],self.esxi_credentials['passwd'], self)
        command = "nsxcli uplink/connect {}".format(interface)
        stdin, stdout, stderr = ssh.exec_command(command)
        stderr_data = stderr.read()
        if len(stderr_data) > 0:
            ssh.close()
            print "ERROR: {}".format(stderr_data)
            return False
        ssh.close()
        print "connected interface '{}' on ESXI host '{}'".format(interface, esx_host.name)
        return True

    def wait_for_tasks(self, tasks):
        """Given the service instance si and tasks, it returns after all the
       tasks are complete
       """
        property_collector = self.vc_connection.content.propertyCollector
        task_list = [str(task) for task in tasks]
        # Create filter
        obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                     for task in tasks]
        property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                                   pathSet=[],
                                                                   all=True)
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = obj_specs
        filter_spec.propSet = [property_spec]
        pcfilter = property_collector.CreateFilter(filter_spec, True)
        task_state = None
        try:
            version, state = None, None
            # Loop looking for updates till the state moves to a completed state.
            while len(task_list):
                update = property_collector.WaitForUpdates(version)
                for filter_set in update.filterSet:
                    for obj_set in filter_set.objectSet:
                        task = obj_set.obj
                        for change in obj_set.changeSet:
                            if change.name == 'info':
                                state = change.val.state
                            elif change.name == 'info.state':
                                state = change.val
                            else:
                                continue

                            if not str(task) in task_list:
                                continue

                            if state == vim.TaskInfo.State.success:
                                task_state = True
                                task_list.remove(str(task))
                            elif state == vim.TaskInfo.State.error:
                                raise task.info.error
                                task_state = False
                # Move to next version
                version = update.version
        finally:
            if pcfilter:
                pcfilter.Destroy()
            return task_state



    def _get_all_objs(content, vimtype):
        """
        Get all the vsphere objects associated with a given type, sometimes this takes a long time.
        """
        obj = {}
        container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
        for c in container.view:
            obj.update({c: c.name})
        return obj

    def _get_all_vms(self, content, vimtype):
        """
        Get all the vsphere objects associated with a given type, sometimes this takes a long time.
        """
        obj = {}
        container = content.viewManager.CreateContainerView(content.rootFolder,[vim.VirtualMachine], True)
        for c in container.view:
            obj[c.name] = c
        return obj

    def get_all_vms(self):
        """
        Returns all vms
        """
        return self._get_all_vms(self.vc_connection.RetrieveContent(), [vim.VirtualMachine])


    def get_vm_by_name(self, name):
        """
        Find a virtual machine by it's name and return it
        """
        return self._get_obj(self.vc_connection.RetrieveContent(), [vim.VirtualMachine], name)



    def get_networks(self, host_name=None):
        """
        Gets a dictionary of all networks for all esxi hosts, keyed by network name
        
        Args:
            host_name (str): An optional argument to get only the networks for the host
        
        Returns:
            dict: A dictionary of networks for the vCenter or a single host
        Example: 
        
        """

        networks = {}
        hosts = self.esxi_hosts

        if host_name:
            host = self.get_esxi_host(host_name)
            hosts = [host]

        for host in hosts:
            for network in host.network:
                networks[network.name] = network
        return networks



    def get_network_obj(self, net_match, network_objs):
        for network_name in network_objs.keys():
            if network_name.endswith(net_match):
                return network_objs[network_name]
        return None 




    def update_virtual_nic_state(self, vm_obj, nic_number, new_nic_state='connect', vmnic_mac='', network_obj=''):
        """
        :param vm_obj: Virtual Machine Object
        :param nic_number: Network Interface Controller Number
        :param new_nic_state: Either Connect, Disconnect or Delete
        :return: True if success
        """

        if new_nic_state != 'add':  
            nic_prefix_label = 'Network adapter '
            nic_label = nic_prefix_label + str(nic_number)
            virtual_nic_device = None
            for dev in vm_obj.config.hardware.device:
                if isinstance(dev, vim.vm.device.VirtualEthernetCard) \
                        and dev.deviceInfo.label == nic_label:
                    virtual_nic_device = dev
            if not virtual_nic_device:
                raise RuntimeError('Virtual {} could not be found.'.format(nic_label))

        virtual_nic_spec = vim.vm.device.VirtualDeviceSpec()
        #connectable = vim.vm.device.VirtualDevice.ConnectInfo()


        if new_nic_state == 'connect':
            connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            connectable.connected = True
            connectable.startConnected = True
            virtual_nic_spec.device = virtual_nic_device
            virtual_nic_spec.device.wakeOnLanEnabled = \
                virtual_nic_device.wakeOnLanEnabled
            virtual_nic_spec.device.key = virtual_nic_device.key
            virtual_nic_spec.device.macAddress = virtual_nic_device.macAddress
            virtual_nic_spec.device.backing = virtual_nic_device.backing
            virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        elif new_nic_state == 'disconnect':
            connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            connectable.connected = False
            connectable.startConnected = False
            virtual_nic_spec.device = virtual_nic_device
            virtual_nic_spec.device.wakeOnLanEnabled = \
                virtual_nic_device.wakeOnLanEnabled
            virtual_nic_spec.device.key = virtual_nic_device.key
            virtual_nic_spec.device.macAddress = virtual_nic_device.macAddress
            virtual_nic_spec.device.backing = virtual_nic_device.backing
            virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        elif new_nic_state == 'delete':
            virtual_nic_spec.device = virtual_nic_device
            connectable = virtual_nic_device.connectable
            connectable.connected = False
            connectable.startConnected = False
            virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
        elif new_nic_state == 'add':
            connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            connectable.connected = True
            connectable.startConnected = True
            virtual_nic_spec.device = vim.vm.device.VirtualVmxnet3()
            virtual_nic_spec.device.key = 4000 + nic_number - 1
            virtual_nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo() 
            virtual_nic_spec.device.macAddress = vmnic_mac
            virtual_nic_spec.device.addressType = 'manual'
            virtual_nic_spec.device.backing.deviceName = network_obj.name
            virtual_nic_spec.device.backing.network = network_obj
            virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
         

        else:
            connectable = virtual_nic_device.connectable
        virtual_nic_spec.device.connectable = connectable
        dev_changes = []
        dev_changes.append(virtual_nic_spec)
        spec = vim.vm.ConfigSpec()
        spec.deviceChange = dev_changes
        task = vm_obj.ReconfigVM_Task(spec=spec)
        self.wait_for_tasks([task])
        return True 