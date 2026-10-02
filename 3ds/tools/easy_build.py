"""One-click build of Smash 64 for New 3DS from the user's own ROM (Windows).

"Build Smash 64 CIA.bat" runs tools/easy_build/start.ps1, which fetches a
portable Python into the work folder and starts this script with it. This
fetches portable Git and Pillow, sets up the pinned toolchain, builds both
CIAs with the regular tools, and collects them for the SD card:

  <work>/Smash 64 for 3DS/Copy to SD card/cias/*.cia
  <work>/Smash 64 for 3DS/What to do next.txt
  <work>/build-log.txt                     every tool's full output

Every download is pinned and hash-checked. The ROM, and everything made from
it, stays on this computer. Each step can be repeated: a build that stops
(window closed, connection lost) continues the next time.

  python 3ds/tools/easy_build.py --work C:\\Smash64Build [--rom PATH]
"""
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]  # the builder's copy of the repository
ISSUES = 'https://github.com/2gifts/smash64-3ds/issues'
MINGIT = ('https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.1/MinGit-2.56.0-64-bit.zip',
          '064b440ff870ed5198527e8f3a92cdf5bd2fd0fedf5e718af95e3fdaddeff718')
# Pillow for the HOME Menu icon and banner, for the portable Python 3.14.
WHEELS = [
    ('https://files.pythonhosted.org/packages/f1/e0/492879f69d94f91f60fc8cd05ba03650e9520afebb2fb7aa12777d7c7f38/'
     'pillow-12.3.0-cp314-cp314-win_amd64.whl',
     'fdafc9cce40277e0f7a0feabce0ee50dd2fa1800f3b38015e51296b5e814048d', 'PIL'),
]
ROM_BYTES = 16 << 20
ROM_SHA1 = 'e2929e10fccc0aa84e5776227e798abc07cedabf'  # Super Smash Bros. (USA), revision 1.0, .z64
GAME_FILES = 479  # compiled game source files, for the progress display
CIAS = {'Smash64-New3DS.cia': 'Smash 64 (unlock things by playing)',
        'Smash64-New3DS-Unlocked.cia': 'Smash 64: All Unlocked'}
# Tool outputs and caches in the builder's folder; never copied as source.
NOT_SOURCE = {'.git', 'build', 'dist', 'toolchain', 'assets', 'generated', 'renderer', '__pycache__'}


class Stop(Exception):
    """A problem the user can fix; the message says how."""


# --- console and log --------------------------------------------------------------
LOG = None


def say(text=''):
    print(text, flush=True)
    log(text)


def log(text):
    if LOG:
        LOG.write(text + '\n')
        LOG.flush()


def minutes(seconds):
    m = round(seconds/60)
    return 'less than a minute' if m < 1 else '1 minute' if m == 1 else f'{m} minutes'


def run(args, cwd, env, progress=None):
    """Run a tool with its output in the log; show that it is still working."""
    log('\n$ ' + ' '.join(str(a) for a in args))
    start = time.monotonic()
    shown = start
    process = subprocess.Popen([str(a) for a in args], cwd=cwd, env=env, stdout=LOG, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL)
    while process.poll() is None:
        time.sleep(1)
        if time.monotonic()-shown >= 60:
            shown = time.monotonic()
            extra = progress() if progress else ''
            print(f'      still working ({minutes(shown-start)} so far{extra})', flush=True)
    LOG.flush()
    return process.returncode


def last_log_lines(count=12):
    LOG.flush()
    lines = Path(LOG.name).read_text(encoding='utf-8', errors='replace').splitlines()
    return [line for line in lines if line.strip()][-count:]


# --- downloads ----------------------------------------------------------------------
def download(url, dest, sha256):
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == sha256:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + '.partial')
    request = urllib.request.Request(url, headers={'User-Agent': 'smash64-3ds-easy-build'})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open('wb') as out:
            shutil.copyfileobj(response, out, 1 << 20)
    except OSError as error:
        raise Stop(f'Could not download {url.rsplit("/", 1)[-1]} ({error}).\n'
                   'Check your internet connection, then run the builder again.')
    if hashlib.sha256(partial.read_bytes()).hexdigest() != sha256:
        partial.unlink()
        raise Stop(f'The download of {url.rsplit("/", 1)[-1]} was damaged. Run the builder again.')
    partial.replace(dest)
    return dest


def unzip(archive, dest):
    dest = dest.resolve()
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            target = (dest/entry.filename).resolve()
            if not target.is_relative_to(dest):
                raise Stop(f'Unsafe file in {archive.name}')
        z.extractall(dest)


# --- the ROM --------------------------------------------------------------------------
def pick_rom():
    """A Windows file dialog, in front of the console window."""
    script = ('[Console]::OutputEncoding=[Text.Encoding]::UTF8;'
              'Add-Type -AssemblyName System.Windows.Forms;'
              '$f=New-Object System.Windows.Forms.Form -Property @{TopMost=$true};'
              '$d=New-Object System.Windows.Forms.OpenFileDialog;'
              '$d.Title="Choose your Super Smash Bros. ROM (US, .z64/.n64/.v64)";'
              '$d.Filter="Nintendo 64 ROM (*.z64;*.n64;*.v64)|*.z64;*.n64;*.v64|All files (*.*)|*.*";'
              'if($d.ShowDialog($f) -eq "OK"){$d.FileName}')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-STA', '-Command', script],
                            capture_output=True, encoding='utf-8', errors='replace')
    path = result.stdout.strip()
    return Path(path) if path else None


def big_endian(data):
    """The ROM in .z64 (big-endian) byte order, or None if it is not an N64 ROM."""
    magic = data[:4]
    if magic == b'\x80\x37\x12\x40':
        return data
    if magic == b'\x37\x80\x40\x12':  # .v64: byte-swapped halfwords
        swapped = bytearray(len(data))
        swapped[0::2], swapped[1::2] = data[1::2], data[0::2]
        return bytes(swapped)
    if magic == b'\x40\x12\x37\x80':  # .n64: little-endian words
        swapped = bytearray(len(data))
        for i in range(4):
            swapped[i::4] = data[3-i::4]
        return bytes(swapped)
    return None


def check_rom(path, dest):
    """Plain-language checks, then a .z64 copy for the build tools."""
    if not path.is_file():
        raise Stop(f'The file "{path}" was not found.')
    if path.suffix.lower() in ('.zip', '.7z', '.rar', '.gz'):
        raise Stop('This ROM is packed in an archive. Extract it first, then choose the .z64, .n64 or .v64 file.')
    size = path.stat().st_size
    if size > 64 << 20:
        raise Stop('This file is too large to be a Nintendo 64 ROM. Please choose your Super Smash Bros. ROM.')
    rom = big_endian(path.read_bytes())
    if rom is None:
        raise Stop('This file does not look like a Nintendo 64 ROM. Please choose your Super Smash Bros. ROM.')
    code, revision = rom[0x3b:0x3f], rom[0x3f]
    if code[:3] != b'NAL':
        name = rom[0x20:0x34].decode('ascii', 'replace').strip()
        raise Stop(f'This ROM is "{name}", not Super Smash Bros. Please choose your Super Smash Bros. ROM.')
    if code[3:] != b'E':
        region = {b'J': 'Japanese', b'P': 'European', b'U': 'Australian'}.get(code[3:], 'a non-US')
        raise Stop(f'This is the {region} version of Super Smash Bros. The port needs the US version.')
    if revision != 0 or len(rom) != ROM_BYTES or hashlib.sha1(rom).hexdigest() != ROM_SHA1:
        raise Stop('This US Super Smash Bros. ROM is modified, patched or a different revision.\n'
                   'The port needs an unmodified US revision 1.0 ROM (SHA-1 ' + ROM_SHA1 + ').')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or hashlib.sha1(dest.read_bytes()).hexdigest() != ROM_SHA1:
        dest.write_bytes(rom)


# --- steps ----------------------------------------------------------------------------
class Build:
    def __init__(self, work, rom):
        self.work = work
        self.rom = rom
        self.z64 = work/'rom/baserom.us.z64'
        self.src = work/'source'
        self.python = Path(sys.executable)
        self.git = work/'git'
        self.out = work/'Smash 64 for 3DS'
        self.progress_file = work/'progress.json'
        self.version = (HERE/'BUILDER_VERSION').read_text().strip() if (HERE/'BUILDER_VERSION').exists() else 'dev'
        self.done = self.load_progress()
        env = dict(os.environ)
        env['PATH'] = os.pathsep.join([str(self.git/'cmd'), str(self.python.parent), env.get('PATH', '')])
        env.update(GIT_TERMINAL_PROMPT='0', PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        self.env = env

    def load_progress(self):
        try:
            data = json.loads(self.progress_file.read_text())
            return set(data['done']) if data.get('version') == self.version else set()
        except (OSError, ValueError, KeyError):
            return set()

    def mark(self, name):
        self.done.add(name)
        self.progress_file.write_text(json.dumps(dict(version=self.version, done=sorted(self.done)), indent=2))

    def tool(self, *args, progress=None, fail='A build step failed.'):
        code = run([self.python, *args], self.src/'3ds', self.env, progress)
        if code:
            raise Stop(fail + '\n\nLast lines of the log:\n  ' + '\n  '.join(last_log_lines()))

    # 1
    def source(self):
        """Copy the builder's source into the work folder (short, ASCII path)."""
        marker = self.src/'BUILDER_VERSION'
        if self.src.resolve() == HERE.resolve():
            return
        current = marker.read_text().strip() if marker.exists() else None
        if current == self.version and (self.src/'3ds/tools/build_release.py').exists():
            return
        if current is not None and current != self.version:
            # A different builder version: rebuild, but keep the toolchain
            # (verified again by its own checks).
            for name in ('build', 'assets', 'generated', 'renderer'):
                remove_tree(self.src/'3ds'/name)
            self.done.discard('compile')
        top = str(HERE)
        shutil.copytree(HERE, self.src, dirs_exist_ok=True,
                        ignore=lambda d, names: [n for n in names if n in NOT_SOURCE and
                                                 (Path(d) in (HERE, HERE/'3ds') or n in ('__pycache__', '.git'))])

    # 2
    def prerequisites(self):
        if not (self.git/'cmd/git.exe').exists():
            archive = download(MINGIT[0], self.work/'downloads/MinGit.zip', MINGIT[1])
            shutil.rmtree(self.git, ignore_errors=True)
            unzip(archive, self.git)
        site = Path(sys.prefix)/'Lib/site-packages'
        for url, sha256, module in WHEELS:
            if not (site/module).exists():
                unzip(download(url, self.work/'downloads'/url.rsplit('/', 1)[-1], sha256), site)

    # 3
    def tools(self):
        if 'tools' in self.done and (self.src/'3ds/build-config.json').exists():
            return
        self.tool('tools/bootstrap_toolchain.py',
                  fail='Downloading the build tools failed. Check your internet connection and run the builder again.')
        self.mark('tools')

    # 4
    def compile(self):
        objects = self.src/'3ds/build/objects'

        def progress():
            done = sum(1 for _ in objects.rglob('*.o')) if objects.exists() else 0
            return f', about {min(99, done*100//GAME_FILES)}% of the game compiled'
        self.tool('tools/build_release.py', '--rom', self.z64, progress=progress,
                  fail='Building the game failed.')
        self.mark('compile')

    # 5
    def collect(self):
        built = self.src/'3ds/build/release'
        sd = self.out/'Copy to SD card'
        remove_tree(sd)
        for name in CIAS:
            link_or_copy(built/name, sd/'cias'/name)
        licenses = self.src/'3ds/licenses'
        for path in licenses.glob('*.txt'):
            link_or_copy(path, self.out/'Licenses'/path.name)
        (self.out/'What to do next.txt').write_text(NEXT_STEPS.format(work=self.work), encoding='utf-8')


def remove_tree(path):
    def writable(func, target, _):
        os.chmod(target, 0o700)  # git marks its object files read-only
        func(target)
    if path.exists():
        shutil.rmtree(path, onexc=writable)


def link_or_copy(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.unlink(missing_ok=True)
    try:
        os.link(source, dest)
    except OSError:
        shutil.copyfile(source, dest)


NEXT_STEPS = """Smash 64 for New 3DS - your build is ready
==========================================

1. Put your 3DS's SD card in this computer.

2. Open the "Copy to SD card" folder and copy the "cias" folder inside it to
   the SD card.

3. Safely eject the SD card and put it back in your 3DS.

4. On the 3DS, open FBI, then choose: SD > cias. Install:
     Smash64-New3DS.cia           Smash 64 (unlock things by playing)
     Smash64-New3DS-Unlocked.cia  Smash 64: All Unlocked
   You can install one or both. They keep separate saves.

5. Go back to the HOME Menu and start Smash 64.

Sound needs your console's DSP firmware at /3ds/dspfirm.cdc on the SD card.
Current Luma3DS makes it in Rosalina: press L + Down + Select, then
Miscellaneous options > Dump DSP firmware.

Saves, settings and performance reports are on the SD card in /3ds/ssb64/
(and /3ds/ssb64-unlocked/ for the All Unlocked version).

Updating later: download the newest builder, build again, and install the
new CIA files in FBI. Your saves are kept.

Problems? The full log is {work}\\build-log.txt. Please attach it when
asking for help at https://github.com/2gifts/smash64-3ds/issues
"""


# --- the SD card ------------------------------------------------------------------------
def sd_cards(exclude):
    """Drives that hold a 3DS SD card (a "Nintendo 3DS" folder)."""
    kernel = ctypes.windll.kernel32
    mask = kernel.GetLogicalDrives()
    found = []
    for i in range(26):
        letter = chr(65+i)
        root = Path(f'{letter}:\\')
        if not mask >> i & 1 or letter in exclude or kernel.GetDriveTypeW(f'{letter}:\\') not in (2, 3):
            continue
        try:
            if (root/'Nintendo 3DS').is_dir():
                found.append(root)
        except OSError:
            pass
    return found


def offer_sd_copy(build):
    cards = sd_cards({build.work.drive[:1].upper(), 'C'})
    if not cards:
        say('   No 3DS SD card is plugged in. Copy the files yourself (see "What to do next.txt").')
        return
    card = cards[0]
    say(f'   Found a 3DS SD card in {card}.')
    try:
        answer = input(f'   Copy the CIA files to {card}cias now? Type Y and press Enter (Enter alone skips): ')
    except EOFError:
        answer = ''
    if answer.strip().lower() not in ('y', 'yes'):
        say('   Skipped. Copy the files yourself (see "What to do next.txt").')
        return
    try:
        for path in (build.out/'Copy to SD card/cias').iterdir():
            (card/'cias').mkdir(exist_ok=True)
            shutil.copyfile(path, card/'cias'/path.name)
    except OSError as error:
        log(traceback.format_exc())
        say(f'   Copying to the SD card did not work: {error}')
        say('   Copy the "cias" folder yourself (see "What to do next.txt").')
        return
    say(f'   Done. Safely eject the SD card ({card}) before removing it, then install the CIA files with FBI.')


# --- main ---------------------------------------------------------------------------
def main():
    global LOG
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--rom', type=Path)
    ap.add_argument('--no-sd', action='store_true', help='Do not offer to copy to an SD card')
    ap.add_argument('--no-open', action='store_true', help='Do not open the result folder')
    args = ap.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    LOG = (work/'build-log.txt').open('a', encoding='utf-8', errors='replace')
    log(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} builder {HERE} python {sys.version.split()[0]}')
    started = time.monotonic()
    # Keep the PC from sleeping while this window runs (ES_CONTINUOUS|ES_SYSTEM_REQUIRED).
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        build = Build(work, args.rom)
        say('Step 1 of 6: Checking your ROM')
        if build.rom or not build.z64.exists():
            if not build.rom:
                say('   Choose your Super Smash Bros. ROM in the window that opens...')
                build.rom = pick_rom()
                if not build.rom:
                    raise Stop('No ROM was chosen. Run the builder again and choose your Super Smash Bros. ROM.')
            check_rom(build.rom, build.z64)
            say(f'   OK: {build.rom.name} is Super Smash Bros. (US, revision 1.0)')
        else:
            say('   Using the ROM checked in an earlier run.')
        free = shutil.disk_usage(work).free
        if 'tools' not in build.done and free < 3 << 30:
            raise Stop(f'Not enough free space on {work.drive}: the build needs about 3 GB '
                       f'and {free/(1 << 30):.1f} GB is free.')
        build.source()
        say('Step 2 of 6: Downloading build tools (about 450 MB the first time)')
        build.prerequisites()
        build.tools()
        say('Step 3 of 6: Reading your ROM and compiling the game (5 to 20 minutes)')
        build.compile()
        say('Step 4 of 6: Collecting everything for your SD card')
        build.collect()
        say('Step 5 of 6: Checking the CIA files')
        for name in CIAS:
            path = build.out/'Copy to SD card/cias'/name
            say(f'   {name}: {path.stat().st_size/(1 << 20):.1f} MB, verified')
        say('Step 6 of 6: SD card')
        if args.no_sd:
            say('   Skipped.')
        else:
            offer_sd_copy(build)
        say('')
        say(f'All done in {minutes(time.monotonic()-started)}. Your files are in:')
        say(f'   {build.out}')
        say('Open "What to do next.txt" there for the last steps on your 3DS.')
        if not args.no_open:
            os.startfile(build.out)
        return 0
    except Stop as problem:
        say('')
        say('The build stopped:')
        say(str(problem))
    except KeyboardInterrupt:
        say('\nStopped. Run the builder again to continue where it stopped.')
    except Exception:  # noqa: BLE001 - a bug; keep the details
        log(traceback.format_exc())
        say('')
        say('The build stopped because of an unexpected error:')
        say('   ' + traceback.format_exc().strip().splitlines()[-1])
    say('')
    say(f'The full log is {work}\\build-log.txt')
    say('Run the builder again to retry; finished steps are not repeated.')
    say(f'If it keeps failing, ask for help at {ISSUES} and attach the log.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
