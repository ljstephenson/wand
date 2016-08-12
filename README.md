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

This will install all the other dependencies at the same time. Upgrades can be
performed by adding the `--upgrade` option to the pip command.

If you are going to be developing WAnD, you want to have an editable
installation. Clone the repo and install it:
```
git clone https://github.com/ljstephenson/wand <source-directory>
pip install -e <source-directory>
```

Please develop on a branch other than master (e.g. dev) so that you don't break
things for other people trying to install it! There's a simulation mode for the
server that doesn't require either the wavemeter or the acquisition card to be
installed while developing, but produces data that is similar to real data.

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
`wavemeters/config` for now, and a full breakdown of what the config means is
in the [configuration readme](CONFIGURATION.md)

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

Icon made using resources by [Freepik](http://www.freepik.com "Freepik") from
[www.flaticon.com](http://www.flaticon.com "Flaticon"), licensed by
[CC 3.0 BY](http://creativecommons.org/licenses/by/3.0/ "Creative Commons BY 3.0")
