"""Bounded frame-grid scheduling for contiguous recorded speech blocks."""
import math


def rebalance(timeline, durations, max_speed=1.25, max_shift=1.0, fps=25):
    """Redistribute adjacent speech time without crossing explicit silence gaps.

    Keep block endpoints and word order; reject infeasible budgets or large shifts.
    Returns a copy. It never changes reviewed text or the total video duration.
    """
    result = [dict(row) for row in timeline]
    index = 0
    while index < len(result):
        if index not in durations:
            index += 1
            continue
        end = index + 1
        while end in durations and end < len(result):
            end += 1
        left = round(result[index]['start'] * fps)
        right = round(result[end - 1]['end'] * fps)
        minimum = [math.ceil(durations[i] * fps / max_speed - 1e-8) for i in range(index, end)]
        if sum(minimum) > right - left:
            raise ValueError('Speech block cannot fit within the speed cap')
        cursor = left
        for offset, i in enumerate(range(index, end)):
            desired = round(timeline[i]['end'] * fps)
            upper = right - sum(minimum[offset + 1:])
            boundary = min(max(desired, cursor + minimum[offset]), upper)
            start, finish = cursor / fps, boundary / fps
            if max(abs(start - timeline[i]['start']), abs(finish - timeline[i]['end'])) > max_shift + 1e-8:
                raise ValueError('Required timing shift exceeds the permitted bound')
            result[i].update(start=start, end=finish)
            cursor = boundary
        index = end
    return result
