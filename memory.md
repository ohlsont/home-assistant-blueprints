# System Context

- Heating system type: Air-water "franluftsvarmepump" with fresh air intake and exhaust to a heat exchanger.
- Control path: Virtual temperature fed via Ohmigo; used to block/allow heating during high price periods.
- Primary reference sensor: Bathroom (central location, thermal mass in stone tiles).
- Aux resistive heating behavior: Kicks in at 1 C below setpoint.
- Comfort goals: Bedrooms 19-20 C, living room 22 C; slower recovery at night is OK.
- Secondary system: Daikin air-air heat pump on second floor, centrally placed, heats most of that floor.
- Ohmigo emulates a PT100 room sensor for the heatpump input.
- Heatpump neutral/maintenance target: 20 C.
- Auxiliary heat observed to engage below ~19 C under heavy demand.
- Storage/buffer room is used to absorb cold snaps (cap at 25 C).
