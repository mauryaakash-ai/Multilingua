import math

def slots(segments, total):
    """Preserve source timestamps and silence; reject overlaps rather than hide drift."""
    cursor = 0.0
    for item in segments:
        start, end = float(item['start']), float(item['end'])
        if not all(math.isfinite(x) for x in (start, end)):
            raise ValueError('Nonfinite segment timestamp')
        if start < cursor - 0.001 or end <= start or end > total + 0.05:
            raise ValueError('Segments must be ordered, nonoverlapping and inside the video')
        start = max(cursor, start)
        end = min(end, total)
        if end <= start:
            raise ValueError('Invalid segment duration')
        if start > cursor + 0.001:
            yield {'start': cursor, 'end': start, 'text': '', 'translation': ''}
        yield {**item, 'start': start, 'end': end}
        cursor = end
    if cursor < total - 0.001:
        yield {'start': cursor, 'end': total, 'text': '', 'translation': ''}

def srt_time(value):
    value = round(value * 1000)
    h, value = divmod(value, 3600000)
    m, value = divmod(value, 60000)
    s, ms = divmod(value, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def subtitles(segments):
    entries = []
    for item in segments:
        text = str(item.get('translation', '')).strip()
        if text:
            entries.append(f"{len(entries)+1}\n{srt_time(item['start'])} --> "
                           f"{srt_time(item['end'])}\n{text}\n")
    return '\n'.join(entries)
