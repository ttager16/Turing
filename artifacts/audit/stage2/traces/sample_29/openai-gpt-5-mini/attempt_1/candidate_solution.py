def fault_tolerant_patient_monitoring(
    device_readings: List[Dict[str, Any]], 
    device_config: Dict[str, Any],
    acceptable_ranges: Dict[str, List[float]]
) -> Dict[str, Any]:
    # Initialize outputs
    ward_data: Dict[str, Any] = {}
    device_status: Dict[str, Any] = {}
    validation_failures: List[Dict[str, Any]] = []
    critical_wards: List[str] = []
    fault_recovery_log: List[Dict[str, Any]] = []
    processing_ts = int(time.time())
    if device_readings:
        # Use latest timestamp from readings if present (max)
        try:
            processing_ts = max(int(d.get('timestamp', processing_ts)) for d in device_readings)
        except Exception:
            processing_ts = processing_ts

    # Defaults from device_config
    device_roles = device_config.get('device_roles', {})
    device_metrics_cfg = device_config.get('device_metrics', {})
    ward_requirements_cfg = device_config.get('ward_requirements', {})

    # If no readings, return empty structures except timestamp
    if not device_readings:
        return {
            'ward_data': {},
            'device_status': {},
            'validation_failures': [],
            'critical_wards': [],
            'fault_recovery_log': [],
            'timestamp': processing_ts
        }

    # Organize readings by device; keep latest reading per device (by timestamp)
    latest_by_device: Dict[str, Dict[str, Any]] = {}
    for r in device_readings:
        did = r.get('device_id')
        if did is None:
            continue
        ts = int(r.get('timestamp', 0))
        existing = latest_by_device.get(did)
        if (existing is None) or (ts >= int(existing.get('timestamp', 0))):
            latest_by_device[did] = r

    # Build ward -> devices mapping
    ward_devices: Dict[str, List[str]] = defaultdict(list)
    for did, reading in latest_by_device.items():
        ward = reading.get('ward')
        if ward is None:
            continue
        ward_devices[ward].append(did)

    # Also ensure wards mentioned in config are present
    for w in ward_requirements_cfg.keys():
        if w not in ward_devices:
            ward_devices[w] = []

    # Initialize device_status with defaults, including devices present in config but not in readings
    all_device_ids = set(list(latest_by_device.keys()) + list(device_roles.keys()) + list(device_metrics_cfg.keys()))
    for did in all_device_ids:
        role = device_roles.get(did, 'primary')
        device_status[did] = {
            'status': 'failed',  # assume failed until validated
            'role': role,
            'backup_activated': False,
            'last_successful_reading': None
        }

    # Per-ward aggregated metric accumulation
    ward_metric_values: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    ward_active_devices: Dict[str, List[str]] = defaultdict(list)
    ward_backup_activated: Dict[str, List[str]] = defaultdict(list)
    ward_working_count: Dict[str, int] = defaultdict(int)

    # Track primary->backups mapping by metric within ward: find backups that cover same metrics
    # Build index of devices per ward and their metrics
    devices_metrics_by_ward: Dict[str, Dict[str, List[str]]] = defaultdict(dict)  # ward -> device -> metrics
    for did, reading in latest_by_device.items():
        ward = reading.get('ward')
        if ward is None:
            continue
        metrics = device_metrics_cfg.get(did, list(reading.get('metrics', {}).keys()))
        devices_metrics_by_ward[ward][did] = metrics

    # Validate each device reading
    for did, reading in latest_by_device.items():
        ward = reading.get('ward')
        ts = int(reading.get('timestamp', processing_ts))
        status_flag = reading.get('status', 'active')
        metrics = reading.get('metrics', {}) or {}
        role = device_roles.get(did, 'primary')
        device_metrics = device_metrics_cfg.get(did, list(metrics.keys()))
        device_failed_reasons = []
        any_valid = False

        # If device reported offline or not active treat as failed/missing
        if status_flag not in ('active', 'online', 'ok'):
            device_failed_reasons.append('device_offline')
        # Validate each metric the device is supposed to provide
        for m in device_metrics:
            if m not in metrics:
                # missing reading
                validation_failures.append({
                    'device_id': did,
                    'metric': m,
                    'value': None,
                    'reason': 'missing_data',
                    'timestamp': ts
                })
                device_failed_reasons.append(f'{m}_missing')
                continue
            val = metrics.get(m)
            # If None treat as missing
            if val is None:
                validation_failures.append({
                    'device_id': did,
                    'metric': m,
                    'value': None,
                    'reason': 'missing_data',
                    'timestamp': ts
                })
                device_failed_reasons.append(f'{m}_missing')
                continue
            # Check acceptable range
            if m in acceptable_ranges:
                lo, hi = acceptable_ranges[m]
                try:
                    numeric = float(val)
                    if not (lo <= numeric <= hi):
                        validation_failures.append({
                            'device_id': did,
                            'metric': m,
                            'value': val,
                            'reason': 'out_of_range',
                            'timestamp': ts
                        })
                        device_failed_reasons.append(f'{m}_out_of_range')
                    else:
                        # valid reading
                        any_valid = True
                        ward_metric_values[ward][m].append(numeric)
                except Exception:
                    validation_failures.append({
                        'device_id': did,
                        'metric': m,
                        'value': val,
                        'reason': 'out_of_range',
                        'timestamp': ts
                    })
                    device_failed_reasons.append(f'{m}_out_of_range')
            else:
                # No acceptable range specified: accept as valid if numeric
                try:
                    numeric = float(val)
                    any_valid = True
                    ward_metric_values[ward][m].append(numeric)
                except Exception:
                    validation_failures.append({
                        'device_id': did,
                        'metric': m,
                        'value': val,
                        'reason': 'out_of_range',
                        'timestamp': ts
                    })
                    device_failed_reasons.append(f'{m}_invalid')

        # Determine device status
        if any_valid and not device_failed_reasons:
            device_status[did]['status'] = 'working'
            device_status[did]['last_successful_reading'] = ts
            ward_active_devices[ward].append(did)
            ward_working_count[ward] += 1
        elif any_valid:
            # partially valid: treat as working but note reasons
            device_status[did]['status'] = 'working'
            device_status[did]['last_successful_reading'] = ts
            ward_active_devices[ward].append(did)
            ward_working_count[ward] += 1
            # log primary failure events if primary has some failures
            if role == 'primary' and device_failed_reasons:
                fault_recovery_log.append({
                    'event': 'primary_device_failure',
                    'device_id': did,
                    'ward': ward,
                    'reasons': device_failed_reasons,
                    'timestamp': ts
                })
        else:
            # no valid metrics -> failed
            device_status[did]['status'] = 'failed'
            device_status[did]['last_successful_reading'] = None
            # If primary failed, try to activate backups (later)
            if role == 'primary':
                fault_recovery_log.append({
                    'event': 'primary_device_failure',
                    'device_id': did,
                    'ward': ward,
                    'reasons': device_failed_reasons or ['no_valid_readings'],
                    'timestamp': ts
                })

    # Backup activation: for each ward, for each metric, if there is no valid metric reading from primaries, attempt to use backups
    for ward, metrics_map in ward_metric_values.items():
        pass  # already collected valid readings; we'll check metrics missing per ward below

    # Build mapping of backups per ward that can provide metrics
    for ward, devices in devices_metrics_by_ward.items():
        # For each metric expected in ward (from device configs), determine if ward has valid reading
        # Collect set of all metrics for the ward
        ward_all_metrics = set()
        for d, mets in devices.items():
            for m in mets:
                ward_all_metrics.add(m)
        # For each metric, if there's no valid reading in ward_metric_values, try to activate backups
        for m in ward_all_metrics:
            valid_vals = ward_metric_values[ward].get(m, [])
            if valid_vals:
                continue  # already have valid
            # Find primary devices in ward that cover m and are failed
            primaries_failed = [d for d in devices.keys() if device_roles.get(d, 'primary') == 'primary' and m in devices[d] and device_status.get(d, {}).get('status') == 'failed']
            # Find backups that can provide m and are working (or have readings)
            candidate_backups = [d for d in devices.keys() if device_roles.get(d, 'primary') == 'backup' and m in devices[d]]
            activated = False
            for b in candidate_backups:
                # Look at reading for backup device
                reading = latest_by_device.get(b)
                if not reading:
                    continue
                metrics = reading.get('metrics', {}) or {}
                val = metrics.get(m)
                ts = int(reading.get('timestamp', processing_ts))
                if val is None:
                    validation_failures.append({
                        'device_id': b,
                        'metric': m,
                        'value': None,
                        'reason': 'missing_data',
                        'timestamp': ts
                    })
                    continue
                try:
                    num = float(val)
                except Exception:
                    validation_failures.append({
                        'device_id': b,
                        'metric': m,
                        'value': val,
                        'reason': 'out_of_range',
                        'timestamp': ts
                    })
                    continue
                if m in acceptable_ranges:
                    lo, hi = acceptable_ranges[m]
                    if not (lo <= num <= hi):
                        validation_failures.append({
                            'device_id': b,
                            'metric': m,
                            'value': val,
                            'reason': 'out_of_range',
                            'timestamp': ts
                        })
                        continue
                # Activate this backup
                ward_metric_values[ward][m].append(num)
                # mark backup as activated
                device_status.setdefault(b, {
                    'status': 'working',
                    'role': device_roles.get(b, 'backup'),
                    'backup_activated': True,
                    'last_successful_reading': ts
                })
                device_status[b]['status'] = 'working'
                device_status[b]['backup_activated'] = True
                device_status[b]['last_successful_reading'] = ts
                if b not in ward_active_devices[ward]:
                    ward_active_devices[ward].append(b)
                    ward_working_count[ward] += 1
                if b not in ward_backup_activated[ward]:
                    ward_backup_activated[ward].append(b)
                # log activation for each primary that failed (if any)
                for p in primaries_failed:
                    fault_recovery_log.append({
                        'event': 'backup_activation',
                        'primary_device': p,
                        'backup_device': b,
                        'ward': ward,
                        'timestamp': ts
                    })
                activated = True
                break
            if not activated:
                # No backup could provide valid reading for this metric; nothing to do but metric will be missing
                continue

    # After attempting backup activations, compute ward aggregated metrics
    for ward in ward_devices.keys():
        agg = {}
        mets = ward_metric_values.get(ward, {})
        for m, vals in mets.items():
            if vals:
                agg[m] = sum(vals) / len(vals)
        working_count = ward_working_count.get(ward, 0)
        req = ward_requirements_cfg.get(ward, 1)
        active_list = sorted(list(set(ward_active_devices.get(ward, []))))
        backup_activated_list = sorted(list(set(ward_backup_activated.get(ward, []))))
        # data quality
        if working_count > req:
            dq = 'high'
        elif working_count == req:
            dq = 'medium'
        else:
            dq = 'low'
        if working_count == 0:
            ward_data[ward] = None
        else:
            ward_data[ward] = {
                'aggregated_metrics': agg,
                'working_device_count': working_count,
                'active_devices': active_list,
                'backup_devices_activated': backup_activated_list,
                'data_quality': dq
            }
        if working_count < req:
            critical_wards.append(ward)
            fault_recovery_log.append({
                'event': 'critical_ward_detected',
                'ward': ward,
                'working_device_count': working_count,
                'required': req,
                'timestamp': processing_ts
            })

    # Ensure device_status entries for devices present only in config but no readings remain with appropriate defaults
    for did in device_status.keys():
        # role already set; ensure last_successful_reading integer or None
        if device_status[did].get('last_successful_reading') is not None:
            try:
                device_status[did]['last_successful_reading'] = int(device_status[did]['last_successful_reading'])
            except Exception:
                device_status[did]['last_successful_reading'] = None

    # If no critical wards, return empty list
    if not critical_wards:
        critical_wards = []

    # Sort logs chronologically by timestamp for determinism
    fault_recovery_log.sort(key=lambda x: x.get('timestamp', 0))

    return {
        'ward_data': ward_data,
        'device_status': device_status,
        'validation_failures': validation_failures,
        'critical_wards': critical_wards,
        'fault_recovery_log': fault_recovery_log,
        'timestamp': processing_ts
    }