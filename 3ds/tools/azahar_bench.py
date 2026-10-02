"""Run the bench build in a portable Azahar and summarize its frame timing.

Emulator timing is not New 3DS timing. Use this to compare builds and to see
which part of a frame grows, then confirm on hardware.

  python tools/azahar_bench.py --azahar C:/path/azahar.exe --scene 54 --frames 3600
"""
import argparse
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from build import OUT


def summarize(log, perf):
    text = log.read_text(errors='replace') if log.exists() else ''
    pace = [(int(m[1]), float(m[2]), float(m[3])) for m in
            re.finditer(r'PACE frame=(\d+) fps=([\d.]+) tick_ms=([\d.]+)', text)]
    detail = [dict(kv.split('=') for kv in line.split()[1:]) for line in text.splitlines() if line.startswith('DETAIL ')]
    drops = [int(m[1]) for m in re.finditer(r'audio_drops=(\d+)', text)]
    underruns = [int(m[1]) for m in re.finditer(r'audio_underruns=(\d+)', text)]
    queued = [int(m[1]) for m in re.finditer(r'audio_queued=(\d+)', text)]
    scenes = [int(m[1]) for m in re.finditer(r'SCENE frame=\d+ current=(\d+)', text)]
    out = {'scenes': scenes}
    if pace:
        steady = pace[5:] or pace
        fps = [p[1] for p in steady]
        out.update(fps_mean=round(statistics.mean(fps), 2), fps_min=round(min(fps), 2),
                   tick_ms_mean=round(statistics.mean(p[2] for p in steady), 3),
                   tick_ms_max=round(max(p[2] for p in steady), 3))
    if detail:
        for key in ('wait_ms', 'replay_ms', 'render_ms', 'audio_ms'):
            values = [float(d[key]) for d in detail[5:] or detail if key in d]
            if values:
                out[key+'_mean'] = round(statistics.mean(values), 3)
    if drops:
        out['audio_drops'] = drops[-1]
    if underruns:
        out['audio_underruns'] = underruns[-1]
        out['audio_queued_min_mean_max'] = (min(queued[5:] or queued), round(statistics.mean(queued[5:] or queued)), max(queued))
    for path in sorted(perf.glob('match-*.csv')):
        head = path.read_text(errors='replace').splitlines()[:4]
        stats = next((h for h in head if h.startswith('# active_seconds')), '')
        out.setdefault('matches', []).append(stats[2:])
    for marker in ('ABORT', 'assert', 'Unexpected'):
        if marker in text:
            out['problem'] = next(line for line in text.splitlines() if marker in line)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--azahar', type=Path, required=True)
    ap.add_argument('--app', type=Path, default=OUT/'bench/ssb64-bench.3dsx')
    ap.add_argument('--scene', type=int, default=-1)
    ap.add_argument('--stage', type=int, default=-1)
    ap.add_argument('--fkind', type=int, default=-1)
    ap.add_argument('--frames', type=int, default=3600)
    ap.add_argument('--slider', type=float, default=-1)
    ap.add_argument('--inputs', type=Path, help='Scripted input intervals: begin end buttons x y')
    ap.add_argument('--timeout', type=float, default=600)
    ap.add_argument('--realtime', action='store_true', help='Run at console speed (needed for audio timing)')
    ap.add_argument('--sync-render', action='store_true', help='Render on the main thread (no core-2 render thread)')
    ap.add_argument('--fixed-audio', action='store_true', help='Use the original fixed 60-tic audio pacing')
    ap.add_argument('--keep', type=Path, help='Copy the log and perf files here')
    ap.add_argument('--data', default='ssb64', help='SD folder of the profile (ssb64-unlocked for the unlocked build)')
    ap.add_argument('--keep-save', action='store_true', help='Start with the save already on the emulated SD card')
    args = ap.parse_args()
    user = args.azahar.parent/'user'
    data = user/'sdmc/3ds'/args.data
    data.mkdir(parents=True, exist_ok=True)
    for name in ('game.log', 'test-input.txt', *(() if args.keep_save else ('save.bin', 'save.bak'))):
        (data/name).unlink(missing_ok=True)
    shutil.rmtree(data/'perf', ignore_errors=True)
    (data/'bench.txt').write_text(f'{args.scene} {args.stage} {args.fkind} {args.frames} {args.slider} {int(args.fixed_audio)} {int(args.sync_render)}\n')
    if args.inputs:
        shutil.copy2(args.inputs, data/'test-input.txt')
    config = user/'config/qt-config.ini'
    if config.exists():
        text = re.sub(r'(?m)^frame_limit=\d+$', 'frame_limit='+('100' if args.realtime else '0'), config.read_text())
        config.write_text(text)
    proc = subprocess.Popen([str(args.azahar), str(args.app.resolve())])
    log = data/'game.log'
    start = time.monotonic()
    try:
        while time.monotonic()-start < args.timeout and proc.poll() is None:
            time.sleep(2)
            if log.exists() and 'EXIT frames=' in log.read_text(errors='replace'):
                time.sleep(2)
                break
    finally:
        proc.kill()
    result = summarize(log, data/'perf')
    result['wall_seconds'] = round(time.monotonic()-start, 1)
    if args.keep:
        args.keep.mkdir(parents=True, exist_ok=True)
        for path in [log, data/'save.bin', *(data/'perf').glob('*.csv')]:
            if path.exists():
                shutil.copy2(path, args.keep/path.name)
    for key, value in result.items():
        print(f'{key}: {value}')


if __name__ == '__main__':
    main()
