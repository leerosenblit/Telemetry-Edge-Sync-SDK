"""Optional integrations that bridge a specific device to the generic SDK.

These are thin, device-specific helpers; the SDK core stays generic. The
solar-race helper, for example, flattens a SolarRace-OS `vehicle_state` dict
into `track()` calls.
"""
