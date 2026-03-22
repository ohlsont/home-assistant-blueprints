# Home Heating Architecture

## Heat Pump

- Model: Qvantum ETK6500 (exhaust-air / franluftsvärmepump)
- Capacity: 6.5 kW (compressor), 5 kW electric backup (3 stages: 1+2+2 kW)
- Serves: radiators + floor heating (combined system) + domestic hot water
- Control: built-in touchscreen, indoor temp setpoint (BOR-värde), managed via `input_number.blockheat_bor`
- Max return temp: 48C (radiator), 35C recommended for floor heating
- External room sensor: Ohmigo (replaces built-in Pt100 duct sensor)
  - Ohmigo reports room temperature to HA via WiFi
  - Blockheat writes target temperature to Ohmigo entity in HA
  - The heat pump reads from Ohmigo as its external Pt100 room sensor

## External Thermometer - Ohmigo

- Product: Ohmigo OHM-ON WiFi (https://www.ohmigo.io/product-page/ohmigo-ohm-on-wifi)
- Role: external room temperature sensor for the ETK6500
- Connected to ETK6500 terminal block pins 7, 8, 9 (replacing built-in duct sensor)
- Also exposed to HA as a WiFi entity - Blockheat writes its computed target here
- HA entity: `number.ohmigo_temperature_2`

## How Blockheat Controls Temperature

1. Blockheat engine computes a target temperature based on policy (price, PV, time windows)
1. Runtime writes the target to the Ohmigo HA entity (`number.ohmigo_temperature_2`)
1. The Ohmigo device physically reports this value to the ETK6500 as "room temperature"
1. The ETK6500 compares this reported temp against its BOR-värde (setpoint, from `input_number.blockheat_bor`)
1. If reported temp < setpoint: heat pump runs; if reported temp > setpoint: heat pump stops
1. This is an indirect control loop: Blockheat doesn't control the heat pump directly,
   it influences the heat pump's own thermostat by manipulating the room temp reading

## Heating Distribution

- Radiators (most rooms)
- Floor heating (some rooms, via shunt groups)
- Combined system: radiator max 48C, floor heating max 35C

## Other Climate Devices

- Daikin AP75809: split AC (living room), controlled separately
- Electrolux WP71-265WT: portable AC (currently unavailable)
