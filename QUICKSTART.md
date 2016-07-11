# Quick Start

Just the commands you need to run to get up and running.

* Install conda
* Create conda environment
    ```
    conda create -n <name> python=3.5 numpy pyqt pyqtgraph -c defaults --override-channels
    ```
* Activate conda environment
  - Windows:
    ```
    activate <name>
    ```
  - 'Nix:
    ```
    source activate <name>
    ```
* Install WAnD
    ```
    pip install https://github.com/ljstephenson/wand/zipball/master
    ```
* Run
  - Server:
    ```
    wand_server <server-config> [-s|--simulation]
    ```
  - Client:
    ```
    wand_client <client-config>
    ```
