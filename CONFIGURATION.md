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

* Version: **new in v2.0** indicates the version of the software that the
  config is intended to run on. Will cause failure to start if there is a major
  version mismatch, warn on minor mismatch (indicating that some features may
  not work) and ignores the patch number

```
    "version":"2.0.0",
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
  one for blue and one for red (although in principle it wouldn't be hard to
  add more). The values for input and trigger are lab specific, since the NI
  cards are connected differently. The lab specific config on the shared area
  is currently correct as of 2016-06-28.
  **coming soon** 'holdoff' and 'period' options to fine tune the exact section
  of the etalon scan which is displayed.

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
    on to a different wavemeter, just copy across the config for that channel
    so that the logs still refer to it with the same name.
  - **new in v2.0** removed the requirement of the redundant *name* field
  - *reference*: reference frequency to use when calculating detuning
  - *exposure*: wavemeter exposure in ms
  - *number*: channel number on switcher that laser is located on
  - *array*: wavemeter has multiple CCD arrays, but only array 1 seems to ever
    be used
  - *blue*: use true if you want the blue etalon for the OSA
  - *active*: **new in v2.0** allows you to tell the server to ignore a
    channel, so that you can leave configuration in file for lasers which are
    still connected but likely to be off long term

```
    "channels":{
        "T1-397":{
            "reference":755.2224,
            "exposure":10,
            "number":1,
            "array":1,
            "blue":true,
            "active":true
        },
```

## Client config

Line by line:

* Name: **new in v2.0** not used by the server any more, so can have multiple
  clients with the same name connected

```
{
    "name":"TestClient3",
```

* Version: **new in v2.0** indicates the version of the software that the
  config is intended to run on. Will cause failure to start if there is a major
  version mismatch, warn on minor mismatch (indicating that some features may
  not work) and ignores the patch number

```
    "version":"2.0.0",
```

* Servers: list of servers to connect to
  - servers are indexed by their name, so it must be unique within the client
    file. It's helpful (but not strictly required) to match the name in the
    server config for ease of use
  - each server has a list of the unique channel names we'd like to receive
    updates about. This need not be the full list of channels provided by that
    server, but the names **must** match those in the server config
  - **new in v2.0** each channel should be given an alias, which will be used
    when displaying the channel

```
    "servers":{
        "TestServer1":{
            "host":"localhost",
            "port":8888,
            "channels":{
                "T1-393":{"alias":"393"},
                "T1-397":{"alias":"397"},
                "T1-850":{"alias":"850"},
                "T1-854":{"alias":"854"},
                "T1-866":{"alias":"866"},
                "T1-RaSlv":{"alias":"RaSlv"},
                "T1-RaMst":{"alias":"RaMst"}
                }
            },
        "TestServer2":{
            "host":"localhost",
            "port":8889,
            "channels":{
                "T2-423":{"alias":"423"}
                }
            }
        },
```

* Layout: Finally this is where you organise the on-screen layout of the GUI.
  The channels appear in movable tabs anyway so this isn't binding, just the
  default on startup. Here we have two rows of 4 channels, to mirror the old
  setup. There's some basic error checking to ensure that the aliases
  here have a corresponding long name entry

```
    "layout":[
            ["397", "393", "RaSlv", "RaMst"],
            ["866", "854", "850", "423"]
        ]
}
```
