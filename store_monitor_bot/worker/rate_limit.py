import time
from typing import Dict

PER_SECOND_LIMIT = int(__import__('os').environ.get('NOTIFY_PER_SECOND', '5'))
PER_MINUTE_LIMIT = int(__import__('os').environ.get('NOTIFY_PER_MINUTE', '60'))
GLOBAL_PER_SECOND = int(__import__('os').environ.get('NOTIFY_GLOBAL_PER_SECOND', '50'))
GLOBAL_PER_MINUTE = int(__import__('os').environ.get('NOTIFY_GLOBAL_PER_MINUTE', '1200'))


def _time_key(suffix: str, window: int):
    t = int(time.time() / window)
    return f"notify:rate:{suffix}:{window}:{t}"


def reserve_notification_slot(redis, payload: Dict) -> bool:
    recipient = payload.get('recipient') or 'global'
    pipe = redis.pipeline()
    k_r_sec = _time_key(f"rec:{recipient}:sec", 1)
    k_r_min = _time_key(f"rec:{recipient}:min", 60)
    k_g_sec = _time_key("global:sec", 1)
    k_g_min = _time_key("global:min", 60)

    pipe.incr(k_r_sec, 1)
    pipe.expire(k_r_sec, 3)
    pipe.incr(k_r_min, 1)
    pipe.expire(k_r_min, 65)
    pipe.incr(k_g_sec, 1)
    pipe.expire(k_g_sec, 3)
    pipe.incr(k_g_min, 1)
    pipe.expire(k_g_min, 65)
    vals = pipe.execute()

    r_sec = int(vals[0])
    r_min = int(vals[2])
    g_sec = int(vals[4])
    g_min = int(vals[6])

    if r_sec > PER_SECOND_LIMIT or r_min > PER_MINUTE_LIMIT:
        return False
    if g_sec > GLOBAL_PER_SECOND or g_min > GLOBAL_PER_MINUTE:
        return False
    return True
