from collections import deque
from typing import Dict, List, Union

def compute_dcei(temperature_readings, power_readings, window_size) -> Dict[str, Union[List[float], str]]:
    # Validation: a) readable lengths, b) both empty or mismatch, c) window size, d) types and ranges
    try:
        n_t = len(temperature_readings)
        n_p = len(power_readings)
    except Exception:
        return {'error': 'Unprocessable readings'}
    if n_t == 0 and n_p == 0:
        return {'error': 'No data provided'}
    if (n_t == 0) != (n_p == 0):
        return {'error': 'Mismatched input lengths'}
    if n_t != n_p:
        return {'error': 'Mismatched input lengths'}
    if not isinstance(window_size, int) or window_size <= 0 or window_size > n_t:
        return {'error': 'Invalid window size'}
    if not isinstance(temperature_readings, list) or not isinstance(power_readings, list):
        return {'error': 'Unprocessable readings'}
    if n_t < 0 or n_t > 100000:
        return {'error': 'Unprocessable readings'}
    for x in temperature_readings:
        if not isinstance(x, int) or isinstance(x, bool) or x < -1000 or x > 1000:
            return {'error': 'Unprocessable readings'}
    for x in power_readings:
        if not isinstance(x, int) or isinstance(x, bool) or x < -1000 or x > 1000:
            return {'error': 'Unprocessable readings'}

    # Deques store indices: temp max/min, power max/min
    temp_max = deque()
    temp_min = deque()
    power_max = deque()
    power_min = deque()

    results: List[float] = []
    n = n_t
    w = window_size

    for i in range(n):
        # Expire indices outside the window
        expire_idx = i - w
        while temp_max and temp_max[0] <= expire_idx:
            temp_max.popleft()
        while temp_min and temp_min[0] <= expire_idx:
            temp_min.popleft()
        while power_max and power_max[0] <= expire_idx:
            power_max.popleft()
        while power_min and power_min[0] <= expire_idx:
            power_min.popleft()

        # Maintain monotonicity and append current index
        while temp_max and temperature_readings[temp_max[-1]] <= temperature_readings[i]:
            temp_max.pop()
        temp_max.append(i)
        while temp_min and temperature_readings[temp_min[-1]] >= temperature_readings[i]:
            temp_min.pop()
        temp_min.append(i)
        while power_max and power_readings[power_max[-1]] <= power_readings[i]:
            power_max.pop()
        power_max.append(i)
        while power_min and power_readings[power_min[-1]] >= power_readings[i]:
            power_min.pop()
        power_min.append(i)

        # Compute when window is full
        if i >= w - 1:
            temp_fluct = temperature_readings[temp_max[0]] - temperature_readings[temp_min[0]]
            power_delta = power_readings[power_max[0]] - power_readings[power_min[0]]
            if power_delta == 0:
                return {'error': 'Division by zero detected'}
            if temp_fluct == 0:
                return {'error': 'Undefined fluctuation'}
            results.append(round(temp_fluct / power_delta, 2))

    # Result length check
    if len(results) != n - w + 1:
        return {'error': 'Invalid window size'}

    return {'result': results}

if __name__ == "__main__":
    temps = [32, 30, 28, 31, 35, 33, 29]
    powers = [100, 102, 101, 99, 97, 95, 94]
    w = 3
    print(compute_dcei(temps, powers, w))