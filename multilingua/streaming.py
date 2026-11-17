"""Deterministic scheduling analysis, not a real-time inference implementation."""
import math

def simulate(arrivals, processing_seconds, max_waiting=3):
    if len(arrivals)!=len(processing_seconds) or max_waiting<1:
        raise ValueError('Mismatched inputs or invalid queue bound')
    previous=-1.0
    finish=0.0
    rows=[]
    for index,(arrival,cost) in enumerate(zip(arrivals,processing_seconds)):
        if not all(math.isfinite(x) for x in (arrival,cost)) or arrival<0 or arrival<previous or cost<0:
            raise ValueError('Arrivals must be ordered and costs finite/nonnegative')
        # Count jobs not yet started; the active job is not a waiting slot.
        waiting=sum(row['start']>arrival for row in rows)
        if finish>arrival and waiting>=max_waiting:
            raise OverflowError(f'Queue bound exceeded at chunk {index}; stream cannot sustain input')
        start=max(arrival,finish);finish=start+cost
        rows.append({'chunk':index,'arrival':arrival,'start':start,'finish':finish,
                     'queue_seconds':start-arrival,'ready_delay_seconds':finish-arrival})
        previous=arrival
    return rows
