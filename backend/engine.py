"""Deterministic rules. State is persisted atomically with each reading."""
def initial_state():
    return {'digital': {}, 'thresholds': {}, 'faults': []}

def evaluate(state, sample, rules):
    events = []
    def emit(kind, severity, message, transition=None, value=None):
        events.append(dict(event_type=kind, severity=severity, message=message, transition=transition, value=value))
    faults = [k for k in ('temperature', 'humidity', 'motion', 'door_open', 'gas') if sample[k] is None]
    if not sample['gas_ready']:
        faults.append('gas_not_ready')
    old_faults = set(state.get('faults', []))
    for fault in sorted(set(faults) - old_faults):
        emit('SENSOR_FAULT', 'WARNING', fault + ' unavailable')
    for fault in sorted(old_faults - set(faults)):
        emit('SENSOR_RECOVERED', 'INFO', fault + ' recovered')
    state['faults'] = faults
    for field, on_type, off_type in [('motion', 'MOTION_DETECTED', 'MOTION_CLEARED'), ('door_open', 'DOOR_OPENED', 'DOOR_CLOSED')]:
        st = state['digital'].setdefault(field, {'stable': False, 'candidate': None, 'count': 0})
        value = sample[field]
        if value is None:
            st['candidate'], st['count'] = None, 0
            continue
        if value == st['stable']:
            st['candidate'], st['count'] = None, 0
        else:
            st['count'] = st['count'] + 1 if st['candidate'] == value else 1
            st['candidate'] = value
            if st['count'] >= rules['digital_samples']:
                st['stable'], st['count'] = value, 0
                emit(on_type if value else off_type, 'INFO', field + (' active' if value else ' inactive'))
    for field, kind in [('temperature', 'HIGH_TEMPERATURE'), ('gas', 'GAS_ALERT')]:
        st = state['thresholds'].setdefault(field, {'active': False, 'count': 0})
        value = sample[field]
        if value is None or (field == 'gas' and not sample['gas_ready']):
            st['count'] = 0  # Invalid input never clears an active condition.
            continue
        crossed = value < rules[field + '_clear'] if st['active'] else value > rules[field + '_high']
        st['count'] = st['count'] + 1 if crossed else 0
        if st['count'] >= rules['confirm_samples']:
            st['active'], st['count'] = not st['active'], 0
            emit(kind, 'CRITICAL' if field == 'gas' else 'WARNING', kind.replace('_', ' ').title() + (' activated' if st['active'] else ' cleared'), 'active' if st['active'] else 'clear', value)
    return events

def reset_candidates(state):
    for st in state['digital'].values():
        st['candidate'], st['count'] = None, 0
    for st in state['thresholds'].values():
        st['count'] = 0
