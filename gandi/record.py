class DNSRecord():
    def __init__(self,
                 name: str,
                 type: str,
                 ttl: int,
                 value: str,
                 ):

        assert isinstance(name, str)
        assert isinstance(type, str)
        assert isinstance(ttl, int)
        assert isinstance(value, str)

        self.name = name
        self.type = type
        self.ttl = ttl
        self.value = value

    @property
    def hash(self):
        _data = {
            'name': self.name,
            'type': self.type,
            'ttl': self.ttl,
            'value': self.value,
        }

        return _data

    def __repr__(self):
        return '<DNSRecord> %s' % self.hash

    def __getitem__(self, item):
        return self.__dict__[item]

    def __eq__(self, other):
        if isinstance(other, DNSRecord):
            return self.hash == other.hash
        return NotImplemented

    def __hash__(self):
        return self.hash

