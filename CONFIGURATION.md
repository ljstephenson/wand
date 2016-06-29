# Configuration Readme

Both client and server use a JSON file to store their configuration. This can
be edited manually but will require a restart of the program.

Example config files can be found in `wand/resources`.

## Server config

Line by line boring breakdown:

* Name: Should be unique.
```
{
    "name":TestServer1,
```

* Host, Port: this is the address that clients will connect to
```
    "host":"localhost",
    "port":8888,
```

* InfluxDB: location of InfluxDB server and parameters needed to connect to it
```
    "influxdb":{
        "host":"10.255.6.112",
        "port":8086,
        "username":"***",
        "password":"***",
        "database":"db"
    },
```

* Switcher: can use either the built in wavemeter switcher or the leoni fibre
switcher
```
    "switcher":{
        "name":"wavemeter"
    },
```
OR
```
    "switcher":{
        "name":"leoni",
        "kwargs":{
            "host":"10.255.6.93",
            "port":10001
        }
    },
```

* OSA: I've made the assumption that there won't be any more than 2 etalons,
one for blue and one for red (although in principle it wouldn't be hard to add
more). The values for input and trigger are lab specific, since the NI cards
are connected differently. The lab specific config on the shared area is
currently correct as of 2016-06-28.
```
    "osa":{
        "blue":{
            "input":"/Dev1/ai0",
            "trigger":"/Dev1/PFI0"
        },
        "red":{
            "input":"/Dev1/ai1",
            "trigger":"/Dev1/PFI2"
        }
    },
```

* Mode: The server can be configured to use only one of OSA/Wavemeter - this
is because we aren't sure if the old lab wavemeter crashing is down to the NI
card, so it's nice to play around with.
```
    "mode":[
        "wavemeter",
        "osa"
    ],
```

* Channel config:
  - laser name must be unique *across the entire system*. If we move a laser
on to a different wavemeter, just copy across the config for that channel so
that the logs still refer to it with the same name.
  - dictionary key *must* match "name" - there is some basic checking to
ensure that this is the case
  - reference: reference frequency to use when calculating detuning
  - exposure: wavemeter exposure in ms
  - number: channel number on switcher that laser is located on
  - array: wavemeter has multiple CCD arrays, but only array 1 seems to ever
be used
  - blue: use true if you want the blue etalon for the OSA
```
    "channels":{
        "T1-397":{
            "name":"T1-397",
            "reference":755.2224,
            "exposure":10,
            "number":1,
            "array":1,
            "blue":true
        },
```

## Client config

Line by line:

* Name: Currently this must be unique per server. An enhancement is under way
so that this is not the case.
```
{
    "name":"TestClient3",
```

* Servers: list of servers to connect to
  - servers are indexed by their name, which must match that in the server
config file. There isn't currently a way to check this and I don't intend to 
implement one, just get it right!
  - each server has a list of the unique channel names we'd like to receive
updates about. This need not be the full list of channels provided by that
server, but the names must match those in the server config
```
    "servers":{
        "TestServer1":{
            "host":"localhost",
            "port":8888,
            "channels":[
                "T1-393",
                "T1-397",
                "T1-850",
                "T1-854",
                "T1-866",
                "T1-RaSlv",
                "T1-RaMst"
                ]
            },
        "TestServer2":{
            "host":"localhost",
            "port":8889,
            "channels":[
                "T2-423"
                ]
            }
        },
```

* Short names: Each of the unique names may be given a shortened name for
the GUI display. These need only be unique on a per-client basis, and can be
whatever the hell you feel like. There's some basic error checking to make sure
that the long names appear somewhere in the server provided list
```
    "short_names":{
            "393":"T1-393",
            "397":"T1-397",
            "850":"T1-850",
            "854":"T1-854",
            "866":"T1-866",
            "RaSlv":"T1-RaSlv",
            "RaMst":"T1-RaMst",
            "423":"T2-423"
        },
```

* Layout: Finally this is where you organise the on-screen layout of the GUI.
The channels appear in movable tabs anyway so this isn't binding, just the
default on startup. Here we have two rows of 4 channels, to mirror the old
setup. Again there's some basic error checking to ensure that short names
here have a corresponding long name entry
```
    "layout":[
            ["397", "393", "RaSlv", "RaMst"],
            ["866", "854", "850", "423"]
        ]
}
```
