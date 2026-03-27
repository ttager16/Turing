def fault_tolerant_patient_monitoring(
    device_readings: List[Dict[str, Any]], 
    device_config: Dict[str, Any],
    acceptable_ranges: Dict[str, List[float]]
) -> Dict[str, Any]:
    # Prepare outputs
    ward_data: Dict[str, Any] = {}
    device_status: Dict[str, Any] = {}
    validation_failures: List[Dict[str, Any]] = []
    critical_wards: List[str] = []
    fault_recovery_log: List[Dict[str, Any]] = []
    # timestamp: use max timestamp from readings or current time if none
    if not device_readings:
        return {
            'ward_data': {},
            'device_status': {},
            'validation_failures': [],
            'critical_wards': [],
            'fault_recovery_log': [],
            'timestamp': int(time.time())
        }
    ts = max(r.get('timestamp', int(time.time())) for r in device_readings)
    # configs
    roles = device_config.get('device_roles', {}) if device_config else {}
    dev_metrics_cfg = device_config.get('device_metrics', {}) if device_config else {}
    ward_requirements_cfg = device_config.get('ward_requirements', {}) if device_config else {}
    default_min = 1
    # organize readings by device and ward
    readings_by_device = {}
    wards_devices = defaultdict(list)
    for r in device_readings:
        did = r.get('device_id')
        ward = r.get('ward')
        readings_by_device[did] = r
        if ward:
            wards_devices[ward].append(did)
    # Initialize device_status with devices seen in readings and configs
    all_device_ids = set(list(readings_by_device.keys()) + list(roles.keys()) + list(dev_metrics_cfg.keys()))
    for did in all_device_ids:
        device_status[did] = {
            'status': 'failed',
            'role': roles.get(did, 'primary'),
            'backup_activated': False,
            'last_successful_reading': None
        }
    # per-ward aggregation helpers
    ward_metric_values = defaultdict(lambda: defaultdict(list))
    ward_active_devices = defaultdict(list)
    ward_backup_activated = defaultdict(list)
    ward_working_counts = defaultdict(int)
    # Map primary->list of backups (from device_config roles and same metrics & ward)
    ward_device_roles = defaultdict(lambda: {'primary': [], 'backup': []})
    # build role lists by ward using readings or config
    for did in all_device_ids:
        # determine ward for device from readings, fallback to None
        ward = readings_by_device.get(did, {}).get('ward')
        role = roles.get(did, 'primary')
        if ward:
            ward_device_roles[ward][role].append(did)
    # Validate each device reading
    for did, r in readings_by_device.items():
        ward = r.get('ward')
        status = r.get('status', 'active')
        metrics = r.get('metrics', {}) or {}
        timestamp = r.get('timestamp', ts)
        role = roles.get(did, 'primary')
        if status != 'active':
            # mark failed due to offline
            device_status[did]['status'] = 'failed'
            device_status[did]['role'] = role
            device_status[did]['last_successful_reading'] = None
            fault_recovery_log.append({
                'event': 'device_offline',
                'device_id': did,
                'ward': ward,
                'timestamp': timestamp
            })
            continue
        # check metrics expected for device from config or infer from provided metrics
        expected_metrics = dev_metrics_cfg.get(did, list(metrics.keys()))
        any_valid = False
        reasons = []
        for m in expected_metrics:
            if m not in metrics:
                validation_failures.append({
                    'device_id': did,
                    'metric': m,
                    'value': None,
                    'reason': 'missing_data',
                    'timestamp': timestamp
                })
                reasons.append(f'{m}_missing')
                continue
            val = metrics[m]
            ar = acceptable_ranges.get(m)
            if ar is None:
                # if no acceptable range given, accept
                valid = True
            else:
                try:
                    valid = (ar[0] <= val <= ar[1])
                except Exception:
                    valid = False
            if not valid:
                validation_failures.append({
                    'device_id': did,
                    'metric': m,
                    'value': val,
                    'reason': 'out_of_range',
                    'timestamp': timestamp
                })
                reasons.append(f'{m}_out_of_range')
            else:
                # valid reading -> include in ward aggregation
                any_valid = True
                ward_metric_values[ward][m].append(val)
        if any_valid:
            device_status[did]['status'] = 'working'
            device_status[did]['role'] = role
            device_status[did]['last_successful_reading'] = timestamp
            ward_active_devices[ward].append(did)
            ward_working_counts[ward] += 1
        else:
            device_status[did]['status'] = 'failed'
            device_status[did]['role'] = role
            device_status[did]['last_successful_reading'] = None
            # log primary failure and attempt backup activation
            if role == 'primary':
                fault_recovery_log.append({
                    'event': 'primary_device_failure',
                    'device_id': did,
                    'ward': ward,
                    'reasons': reasons or ['unknown'],
                    'timestamp': timestamp
                })
                # find backups in same ward that monitor overlapping metrics
                backups = [b for b in ward_device_roles[ward]['backup']]
                # If config didn't list backups, find any device in same ward with role backup
                if not backups:
                    backups = [d for d in all_device_ids if (readings_by_device.get(d, {}).get('ward') == ward and roles.get(d, 'primary') == 'backup')]
                # activate suitable backup(s)
                for b in backups:
                    # if backup has working status already, mark activated
                    rb = readings_by_device.get(b)
                    if not rb:
                        continue
                    # check if backup had any valid metrics (we already processed b maybe after; ensure backup is working)
                    if device_status.get(b, {}).get('status') == 'working':
                        device_status[b]['backup_activated'] = True
                        ward_backup_activated[ward].append(b)
                        fault_recovery_log.append({
                            'event': 'backup_activation',
                            'primary_device': did,
                            'backup_device': b,
                            'ward': ward,
                            'timestamp': timestamp
                        })
                        break
    # Build ward_data
    for ward, metrics_map in ward_metric_values.items():
        agg = {}
        for m, vals in metrics_map.items():
            if vals:
                agg[m] = sum(vals) / len(vals)
        working = ward_working_counts.get(ward, 0)
        req = ward_requirements_cfg.get(ward, default_min)
        if working > req:
            dq = 'high'
        elif working == req:
            dq = 'medium'
        else:
            dq = 'low'
        active_devices = ward_active_devices.get(ward, [])
        backup_activated = list(dict.fromkeys(ward_backup_activated.get(ward, [])))
        ward_data[ward] = {
            'aggregated_metrics': agg if agg else {},
            'working_device_count': working,
            'active_devices': active_devices,
            'backup_devices_activated': backup_activated,
            'data_quality': dq
        }
        if working < req:
            critical_wards.append(ward)
            fault_recovery_log.append({
                'event': 'critical_ward_detected',
                'ward': ward,
                'working_devices': working,
                'required': req,
                'timestamp': ts
            })
    # Include wards that had devices but no working devices -> ward_data None
    # find wards mentioned in readings
    for ward in wards_devices.keys():
        if ward not in ward_data:
            ward_data[ward] = None
            req = ward_requirements_cfg.get(ward, default_min)
            working = ward_working_counts.get(ward, 0)
            if working < req:
                critical_wards.append(ward)
                fault_recovery_log.append({
                    'event': 'critical_ward_detected',
                    'ward': ward,
                    'working_devices': working,
                    'required': req,
                    'timestamp': ts
                })
    # Ensure device_status contains all devices mentioned in config but not in readings
    for did in roles.keys():
        if did not in device_status:
            device_status[did] = {
                'status': 'failed',
                'role': roles.get(did, 'primary'),
                'backup_activated': False,
                'last_successful_reading': None
            }
    # Remove duplicates in critical_wards
    critical_wards = list(dict.fromkeys(critical_wards))
    return {
        'ward_data': ward_data,
        'device_status': device_status,
        'validation_failures': validation_failures,
        'critical_wards': critical_wards,
        'fault_recovery_log': fault_recovery_log,
        'timestamp': ts
    }