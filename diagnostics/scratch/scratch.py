import diagnostics.common as common

def foo(val):
    str = "{}".format(val)
    rts = str[::-1]
    print(rts)


class ClientChannel(common.Channel):
    """
    This was an intersting but hideous way of getting the client to update when
    updating values of the channel
    """
    _attrs = collections.OrderedDict([
            ('name', None),
            ('reference', None),
            ('exposure', None),
            ('frequency', None),
            ('osa', None),
        ])
    # 'name' has no callback since we expect it not to change
    _callbacks = {
            'reference':None,
            'exposure':None,
            'frequency':None,
            'osa':None,
        }

    def add_callback(self, attr, cb):
        # Make sure we are modifying an instance, not class attribute
        if self._callbacks is self.__class__._callbacks:
            self._callbacks = copy(self._callbacks)
        self._callbacks[attr] = cb

    @classmethod
    def add_properties(cls):
        def props(attr):
            internal = "_" + attr
            def getter(self):
                return getattr(self, internal)
            def setter(self, val):
                cb = self._callbacks.get(attr)
                if callable(cb):
                    cb(val)
                setattr(self, internal, val)
            return getter, setter

        for attr in cls._attrs:
            setattr(cls, attr, property(*props(attr)))

# Will be called intentionally on import
ClientChannel.add_properties()