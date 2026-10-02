"""Statistical CPU profile of the bench build in Azahar through its GDB stub.

Interrupts the emulated CPU repeatedly, reads the program counter and the
current scene, and attributes samples to functions and source files. The
emulator's cost per instruction is not the New 3DS's; use the profile to find
hot spots, then measure changes with azahar_bench.py and on hardware.

  python tools/azahar_profile.py --azahar C:/path/azahar.exe --scene 1 --want-scene 61 --samples 4000
"""
import argparse
import collections
import re
import socket
import subprocess
import time
from pathlib import Path

from build import OUT, BIN


class Gdb:
    def __init__(self, port):
        for _ in range(100):
            try:
                self.s = socket.create_connection(('127.0.0.1', port), timeout=10)
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise SystemExit('Could not connect to the Azahar GDB stub')
        self.buf = b''

    def send(self, data):
        packet = b'$' + data + b'#' + b'%02x' % (sum(data) & 0xff)
        self.s.sendall(packet)

    def read_packet(self):
        while True:
            start = self.buf.find(b'$')
            end = self.buf.find(b'#', start)
            if start >= 0 and end >= 0 and len(self.buf) >= end + 3:
                data = self.buf[start+1:end]
                self.buf = self.buf[end+3:]
                self.s.sendall(b'+')
                return data
            chunk = self.s.recv(65536)
            if not chunk:
                raise EOFError
            self.buf += chunk

    def command(self, data):
        self.send(data)
        return self.read_packet()

    def interrupt(self):
        self.s.sendall(b'\x03')
        return self.read_packet()

    def resume(self):
        self.send(b'c')


def symbols(elf):
    out = subprocess.check_output([str(BIN/'llvm-nm.exe'), '-n', '-S', '--defined-only', str(elf)], text=True)
    table = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            table[parts[-1]] = int(parts[0], 16)
    return table


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--azahar', type=Path, required=True)
    ap.add_argument('--app', type=Path, default=OUT/'bench/ssb64-bench.3dsx')
    ap.add_argument('--scene', type=int, default=1, help='Start scene for the bench build')
    ap.add_argument('--stage', type=int, default=-1)
    ap.add_argument('--fkind', type=int, default=-1)
    ap.add_argument('--want-scene', type=int, action='append', help='Only keep samples taken in these scenes')
    ap.add_argument('--samples', type=int, default=3000)
    ap.add_argument('--skip-frames', type=int, default=240, help='Frames to skip after the wanted scene starts (loading)')
    ap.add_argument('--interval', type=float, default=0.004)
    ap.add_argument('--timeout', type=float, default=600)
    ap.add_argument('--port', type=int, default=24689)
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--out', type=Path, help='Write the full profile here')
    args = ap.parse_args()
    user = args.azahar.parent/'user'
    config = user/'config/qt-config.ini'
    text = config.read_text()
    text = text.replace('use_gdbstub\\default=true', 'use_gdbstub\\default=false')
    text = re.sub(r'(?m)^use_gdbstub=\w+$', 'use_gdbstub=true', text)
    text = re.sub(r'(?m)^gdbstub_port=\d+$', f'gdbstub_port={args.port}', text)
    text = re.sub(r'(?m)^frame_limit=\d+$', 'frame_limit=0', text)
    config.write_text(text)
    data = user/'sdmc/3ds/ssb64'
    data.mkdir(parents=True, exist_ok=True)
    (data/'bench.txt').write_text(f'{args.scene} {args.stage} {args.fkind} 0 -1 0\n')
    for name in ('test-input.txt', 'save.bin', 'save.bak'):
        (data/name).unlink(missing_ok=True)
    elf = args.app.with_suffix('.elf')
    table = symbols(elf)
    scene_addr = table['gSCManagerSceneData']
    frame_addr = table['ssb_frame_count']
    proc = subprocess.Popen([str(args.azahar), str(args.app.resolve())])
    pcs = collections.Counter()
    scenes = collections.Counter()
    try:
        gdb = Gdb(args.port)
        gdb.command(b'?')
        gdb.resume()
        start = time.monotonic()
        waiting = bool(args.want_scene)
        while sum(pcs.values()) < args.samples and time.monotonic()-start < args.timeout:
            # Each stop slows emulation: check the scene once a second until
            # the wanted one starts, then sample densely.
            time.sleep(1.0 if waiting else args.interval)
            gdb.interrupt()
            regs = gdb.command(b'g')
            pc = int.from_bytes(bytes.fromhex(regs[15*8:16*8].decode()), 'little')
            mem = gdb.command(b'm%x,1' % scene_addr)
            scene = int(mem[:2], 16) if re.fullmatch(rb'[0-9a-fA-F]+', mem) else -1
            mem = gdb.command(b'm%x,4' % frame_addr)
            frame = int.from_bytes(bytes.fromhex(mem.decode()), 'little') if re.fullmatch(rb'[0-9a-fA-F]{8}', mem) else 0
            gdb.resume()
            scenes[scene] += 1
            if not args.want_scene or scene in args.want_scene:
                if waiting:
                    waiting = False
                    first_frame = frame
                    continue
                if frame < first_frame + args.skip_frames:
                    continue
                pcs[pc] += 1
            elif args.want_scene and not waiting and sum(pcs.values()):
                break  # the wanted scene ended
    finally:
        proc.kill()
        config.write_text(re.sub(r'(?m)^use_gdbstub=\w+$', 'use_gdbstub=false', config.read_text()))
    total = sum(pcs.values())
    print(f'{total} samples kept; scenes sampled: {dict(scenes)}')
    if not total:
        return
    addresses = sorted(pcs)
    result = subprocess.run([str(BIN/'llvm-symbolizer.exe'), f'--obj={elf}', '--output-style=GNU', '--functions=linkage'],
                            input='\n'.join(hex(a) for a in addresses), capture_output=True, text=True).stdout
    lines = result.splitlines()
    by_function = collections.Counter()
    by_file = collections.Counter()
    for i, address in enumerate(addresses):
        function = lines[2*i] if 2*i < len(lines) else '??'
        location = lines[2*i+1] if 2*i+1 < len(lines) else '??'
        source = re.sub(r':\d+(:\d+)?$', '', location).replace('\\', '/')
        source = re.sub(r'^.*?/(smash64-3ds|_buildertest/work/source)/', '', source)
        by_function[function] += pcs[address]
        by_file[source] += pcs[address]
    report = ['== functions']
    report += [f'{100*n/total:6.2f}%  {name}' for name, n in by_function.most_common(args.top)]
    report += ['', '== source files']
    report += [f'{100*n/total:6.2f}%  {name}' for name, n in by_file.most_common(args.top)]
    print('\n'.join(report))
    if args.out:
        args.out.write_text('\n'.join(report) + '\n')


if __name__ == '__main__':
    main()
