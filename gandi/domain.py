import logging
import xmlrpc.client
from . record import DNSRecord


class GandiDomain():
    def __init__(self, apikey, domain, noop: bool=False, exclusive: bool=False, logger=None):
        """ Handle operations for Gandi.net Domain API endpoint
        :param apikey: The API key/token to use
        :param domain: The domain name to operate upon
        """
        assert isinstance(noop, bool)
        assert isinstance(exclusive, bool)

        self.apikey = apikey
        self.domain = domain
        self.noop = noop
        self.exclusive = exclusive

        if logger:
            self.logger = logger.getChild("Domain[%s]" % domain)
        else:
            self.logger = logging.getLogger("Domain[%s]" % domain)

        self.gandi = xmlrpc.client.ServerProxy('https://rpc.gandi.net/xmlrpc/')
        self.logger.debug('Gandi RPC established: api %s' % self.gandi.version.info(self.apikey))

        # Query the API for the zone information
        self.info = self.gandi.domain.info(self.apikey, self.domain)
        self.zoneID = self.info['zone_id']
        self.logger.debug('ZoneID: %s' % self.zoneID)

        self.latest_version = self.zone_version()
        self.instances
        self.resources

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()

    def flush(self):
        """ Compares self._instances to self.resources and does the needful
        """

        self.logger.debug('flushing delta...')

        # Clean up some duplicate junk I caused (we should be able to remove this block soonish
        seen = list()
        self.logger.debug('Cleaning up duplicates')
        for i in self.instances:
            if i.hash not in seen:
                seen.append(i.hash)
            else:
                self.logger.warning('duplicate resource %s' % i)
                self.destroy(i)
        del seen

        self.logger.debug('--- Instances ---')
        for i in self.instances:
            self.logger.debug(i)

        self.logger.debug('--- Resources ---')
        for r in self.resources:
            self.logger.debug(r)


        matched_resources = list()
        unmanaged_instances = list()

        # Loop over instances and match resources
        for instance in self.instances:
            matched_resource = self.match_resource_to_instance(instance)
            if matched_resource:
                matched_resources.append(matched_resource)
            else:
                unmanaged_instances.append(instance)

        for resource in self.resources:
            if resource not in matched_resources:
                if resource not in self.instances:
                    self.create(resource)
            else:
                if resource in self.instances:
                    self.logger.debug('resource in sync %s' % resource)
                else:
                    self.logger.debug('modifying resource %s' % resource)
                    matched_instance = self.match_instance_to_resource(resource)
                    if matched_instance:
                        self.destroy(matched_instance)
                    self.create(resource)

        if self.exclusive:
            for instance in unmanaged_instances:
                self.destroy(instance)

        # If we have ever asked for self.next_version, than we have a new version to commit
        if hasattr(self, '_next_version'):
            self.logger.info('Committing zone version %s' % self.next_version)
            self.gandi.domain.zone.version.set(
                    self.apikey,
                    self.zoneID,
                    self.next_version)

    def match_resource_to_instance(self, instance):
        """ Search self.resources for an instance with the same 'name' and 'type' and return it
        :param instance: The DNSRecord instance
        :return: DNSResource if found, None, if not
        """
        for resource in self.resources:
            if all([instance.hash[attr] == resource.hash[attr] for attr in ['name', 'type']]):
                return resource
        return None

    def match_instance_to_resource(self, resource):
        """ Search self.instances for a resource with the same 'name' and 'type' and return it
        :param resource: The DNSRecord instance
        :return: DNSResource if found, None, if not
        """
        for instance in self.instances:
            if all([instance.hash[attr] == resource.hash[attr] for attr in ['name', 'type']]):
                return instance
        return None

    @property
    def resources(self):
        """ The resources provided by the user
        :return: set of resources
        """
        if not hasattr(self, '_resources'):
            self._resources = list()
        return self._resources

    @property
    def instances(self):
        if not hasattr(self, '_instances'):
            self.logger.debug("initializing instances")
            self._instances = list()
            record_results = self.gandi.domain.zone.record.list(
                    self.apikey,
                    self.zoneID,
                    self.latest_version)

            for record in record_results:
                r = DNSRecord(
                        name=record['name'],
                        type=record['type'],
                        value=record['value'],
                        ttl=int(record['ttl']),
                )

                self._instances.append(r)

            self.logger.debug('discovered instances %s' % self._instances)
        return self._instances

    @property
    def next_version(self):
        """ Creates a new zone version if one is not already found
        :return: identifier for the next zone version
        """
        if not hasattr(self, '_next_version'):
            self._next_version = self.gandi.domain.zone.version.new(
                    self.apikey,
                    self.zoneID)
            self.logger.info("Zone version incremented: %s" % self.next_version)
            return self._next_version
        else:
            return self._next_version

    def add_resource(self, record: DNSRecord):
        """ Adds a DNSRecord object to the inspection list: API entry point to getting a resource into the system
        :param record: A DNSRecord object
        """
        assert isinstance(record, DNSRecord)
        self._resources.append(record)

    def create(self, resource: DNSRecord):
        """ Insert the new record
        :param resource:  DNSRecord instance
        """
        zone_record = {
            "name": resource.name,
            "type": resource.type,
            "ttl": resource.ttl,
            "value": resource.value}


        if self.noop:
            self.logger.info('would create resource %s (noop)' % resource)
        else:
            self.gandi.domain.zone.record.add(
                    self.apikey,
                    self.zoneID,
                    self.next_version,
                    zone_record)
            self.logger.info('created resource %s' % resource)

    def destroy(self, resource: DNSRecord):
        """ Remove a record from from the next zone version
        :param resource: DNSRecord
        :return:
        """
        if self.noop:
            self.logger.info('would destroy resource %s (noop)' % resource)
        else:
            self.logger.info('destroying resource %s' % resource)
            self.gandi.domain.zone.record.delete(
                    self.apikey,
                    self.zoneID,
                    self.next_version,
                    {"name": resource.name, "type": resource.type})

    def refresh_instances(self):
        """ Delete the _instances attribute to cause a refresh from the API
        :return: self._instances
        """
        delattr(self, '_instances')
        return self.instances

    def zone_version(self):
        """ Fetch and return the latest version identifier for the zone
        :return: string containing zone version identifier
        """
        versions = self.gandi.domain.zone.version.list(
            self.apikey,
            self.zoneID
        )

        latest_version = versions[-1]['id']
        self.logger.debug('Latest zone version: {0}'.format(latest_version))
        return latest_version

