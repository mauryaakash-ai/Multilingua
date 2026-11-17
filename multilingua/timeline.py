import math

def validate_segments(segments, total, translated=False):
    if not isinstance(segments, list) or not segments or len(segments) > 500:
        raise ValueError('Supply between 1 and 500 speech segments')
    for index, item in enumerate(segments, 1):
        if not isinstance(item, dict):
            raise ValueError(f'Segment {index} must be an object')
        for name in ('start', 'end'):
            if isinstance(item.get(name), bool) or not isinstance(item.get(name), (int, float)):
                raise ValueError(f'Segment {index}: {name} must be a number')
        for name in ('text', 'translation') if translated else ('text',):
            text = item.get(name)
            if not isinstance(text, str) or not text.strip() or len(text) > 2000:
                raise ValueError(f'Segment {index}: {name} must contain 1–2000 characters')
    list(slots(segments, total))
    return segments

def slots(segments, total):
    """Preserve source timestamps and silence; reject overlaps rather than hide drift."""
    if not math.isfinite(total) or total <= 0:
        raise ValueError('Timeline duration must be positive and finite')
    cursor = 0.0
    for item in segments:
        start, end = float(item['start']), float(item['end'])
        if not all(math.isfinite(x) for x in (start, end)):
            raise ValueError('Nonfinite segment timestamp')
        if start < 0 or start < cursor - 0.001 or end <= start or end > total + 0.05:
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


def frame_slots(segments, total, fps=25):
    """Quantize absolute boundaries once, avoiding cumulative per-cut frame rounding."""
    for item in slots(segments, total):
        start, end = round(item['start'] * fps) / fps, round(item['end'] * fps) / fps
        if end <= start:
            if item.get('translation', '').strip():
                raise ValueError('Speech segment is shorter than one video frame; merge it during review')
            continue
        yield {**item, 'start': start, 'end': end}

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
