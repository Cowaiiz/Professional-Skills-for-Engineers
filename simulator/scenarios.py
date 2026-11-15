"""Deterministic phases: baseline, condition, recovery. No physical hazard needed."""
SCENARIOS = ('normal', 'motion', 'door_open', 'high_temperature', 'high_gas', 'device_unstable', 'combined_event', 'noisy', 'sensor_fault', 'home_showcase')

def values(scenario, tick):
    sample = dict(temperature=27.0 + (tick % 5) / 10, humidity=64.0, gas=400, gas_ready=True, motion=False, door_open=False)
    if scenario == 'home_showcase':
        scenario = 'combined_event' if tick < 23 else 'normal'
    phase = tick % 30
    if 6 <= phase < 20:
        if scenario in ('motion', 'combined_event'):
            sample['motion'] = True
        if scenario in ('door_open', 'combined_event'):
            sample['door_open'] = True
        if scenario in ('high_temperature', 'combined_event'):
            sample['temperature'] = 38.0
        if scenario in ('high_gas', 'combined_event'):
            sample['gas'] = 2600
        if scenario == 'sensor_fault':
            sample['temperature'] = None
        if scenario == 'noisy':
            sample.update(temperature=35.2 if tick % 2 else 34.8, door_open=bool(tick % 2))
    return sample
