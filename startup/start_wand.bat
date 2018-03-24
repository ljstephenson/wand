set server_config=server_config.json
set client_config=client_config.json


call activate wand
start cmd /k "wand_server %server_config%" --ignore_unsecure_ssl
start cmd /k "wand_client %client_config%"
deactivate
