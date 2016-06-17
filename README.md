# WAnD - Wavemeter Analysis 'n' Display

A laser diagnostic system for Oxford Ion Trappers, reading from a National
Instruments Data Acquisition Card and a High Finesse Wavelength Meter. 

## Getting Started

### Prerequisites

We'll be creating this within a conda environment to keep it compartmentalised.
Make sure you have anaconda installed. 

You should check if you have already added the m-labs (artiq) conda channel to
your config - it isn't required but will affect installation:
```
conda config --get channels
```

If your output contains the following, then you have added the channel
```
--add channels 'http:/conda.anaconda.org/m-labs/label/main'
```

### Installation

First create the environment with the modules available to conda. If you don't
care about using Qt5 and are happy with Qt4:
```
conda create -n <name> python=3.5 numpy pyqt pyqtgraph -c defaults --override-channels
```

(The `-c defaults --override-channels` will ignore all but the default
channels in which conda searches for packages, including the m-labs channel)

If you absolutely must use Qt5 and you have the m-labs channel added:
```
conda create -n <name> python=3.5 numpy pyqtgraph quamash
```

Activate your new environment:
Windows:
```
activate <name>
```

'Nix:
```
source activate <name>
```

Now you're ready for the actual install. If you only want to use the software
and don't want to develop it:
```
pip install https://github.com/ljstephenson/wand/zipball/master
```

This will install all the other dependencies at the same time.

If you are going to be developing WAnD, you want to have an editable
installation. Clone the repo and install it:
```
pip install -e <path-to-source>
```

## Testing

Currently filed under 'TODO'... don't treat anything as stable.

## Usage

WAnD uses a client-server model where there is a server per wavemeter computer
collating data. Servers can handle multiple client connections, and clients may
connect to more than one server. Each laser is given a unique name, and
wavemeter readings are automatically pushed to the influxdb server for long
term logging. Clients can configure short names for displaying the unique
laser name.

Configuration files are written in json for human readability - see the
examples. Valid configuration files are on the shared area in
<TODO:put them on the shared area>

Get the config files from the shared area, then on the wavemeter computer:
```
wand_server <server-config> [-s|--simulation]
```

Clients can connect from any computer. Ensure that there isn't a
duplicate client name connected and run:
```
wand_client <client-config>
```

## License

What license?