# Developer tools

## SC3 register inventory

Read every SC3 GLT base address over both Modbus read function codes and write a
stable JSON inventory:

```sh
python -m tools.register_inventory \
  --host 172.16.0.73 \
  --output inventory/solvisleo_180_sc3.json
```

The command only issues FC3 (holding-register) and FC4 (input-register) reads. It
never writes to the controller. Run it again after a firmware or controller change
and compare the generated JSON with the committed inventory.

Use `--map PATH` to probe a different JSON register map, `--port` for a non-default
Modbus TCP port, and `--device-id` for a non-default device id.
