"""Generates the game's sound effects as WAV files (no downloads, no licensing).

Run from anywhere:  python generate_sounds.py
Creates next to this file: fire.wav, explosion.wav, hit.wav, pickup.wav, game_over.wav,
engine_idle.wav, engine_run.wav
"""
import math
import os
import random
import struct
import wave

RATE = 44100
HERE = os.path.dirname(os.path.abspath(__file__))


def save(name, samples, peak=0.9):
    top = max(1e-9, max(abs(s) for s in samples))
    scale = peak / top
    with wave.open(os.path.join(HERE, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * scale)) * 32767)) for s in samples))
    print("wrote", name, f"{len(samples) / RATE:.2f}s")


def lowpass(samples, cutoff_hz):
    """One-pole low-pass filter."""
    a = 1 - math.exp(-2 * math.pi * cutoff_hz / RATE)
    out, y = [], 0.0
    for s in samples:
        y += a * (s - y)
        out.append(y)
    return out


def noise(n, rng):
    return [rng.uniform(-1, 1) for _ in range(n)]


def fire(rng):
    """Tank cannon: sharp crack + deep falling boom + rumbling tail."""
    n = int(0.9 * RATE)
    crack = lowpass(noise(n, rng), 6000)
    rumble = lowpass(lowpass(noise(n, rng), 300), 300)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        freq = 45 + 95 * math.exp(-t / 0.08)  # 140 Hz falling to 45 Hz
        phase += 2 * math.pi * freq / RATE
        boom = math.sin(phase) * math.exp(-t / 0.22)
        attack = min(1.0, t / 0.002)
        out.append(attack * (0.9 * crack[i] * math.exp(-t / 0.025)
                             + 1.0 * boom
                             + 2.2 * rumble[i] * math.exp(-t / 0.3)))
    return out


def explosion(rng):
    """Alien hit: noisy blast with a low thump."""
    n = int(1.0 * RATE)
    body = lowpass(noise(n, rng), 1200)
    low = lowpass(lowpass(noise(n, rng), 180), 180)
    out = []
    for i in range(n):
        t = i / RATE
        thump = math.sin(2 * math.pi * (70 - 30 * t) * t) * math.exp(-t / 0.15)
        out.append(min(1.0, t / 0.004) * (0.8 * body[i] * math.exp(-t / 0.12)
                                           + 0.9 * thump + 2.5 * low[i] * math.exp(-t / 0.35)))
    return out


def hit(rng):
    """Tank rams an alien: metallic clang + crunch + heavy thud."""
    n = int(0.7 * RATE)
    crunch = lowpass(noise(n, rng), 2500)
    # inharmonic partials sound like struck metal
    partials = [(190, 1.0, 0.25), (487, 0.7, 0.18), (811, 0.5, 0.12), (1263, 0.35, 0.08)]
    out = []
    for i in range(n):
        t = i / RATE
        clang = sum(a * math.sin(2 * math.pi * f * t) * math.exp(-t / d) for f, a, d in partials)
        thud = math.sin(2 * math.pi * (75 - 35 * t) * t) * math.exp(-t / 0.09)
        out.append(min(1.0, t / 0.002) * (0.8 * clang + 1.2 * thud + 1.1 * crunch[i] * math.exp(-t / 0.06)))
    return out


def notes(sequence, rng=None):
    """Short melody: list of (frequency Hz, seconds, volume)."""
    out = []
    for freq, secs, vol in sequence:
        n = int(secs * RATE)
        for i in range(n):
            t = i / RATE
            # soft square-ish tone (odd harmonics), quick attack, smooth decay
            tone = sum(math.sin(2 * math.pi * freq * h * t) / h for h in (1, 3, 5))
            env = min(1.0, t / 0.005) * math.exp(-t / (secs * 0.6))
            out.append(vol * tone * env)
    return out


def pickup(rng):
    """Blue ball collected: bright rising arpeggio."""
    return notes([(988, 0.07, 0.8), (1319, 0.07, 0.9), (1976, 0.20, 1.0)])


def game_over(rng):
    """Last life lost: falling 'wah-wah'."""
    return notes([(392, 0.22, 1.0), (330, 0.22, 1.0), (262, 0.22, 1.0), (196, 0.7, 1.0)])


def engine(rng, base_hz, fire_hz, harmonics, noise_amount, seconds=1.0):
    """Seamless engine loop. All frequencies are whole Hz, so a 1 s clip loops without a click."""
    n = int(seconds * RATE)
    # noise layer made loopable by cross-fading its tail into its head
    fade = int(0.2 * RATE)
    raw = lowpass(lowpass(noise(n + fade, rng), 220), 220)
    rumble = raw[:n]
    for i in range(fade):
        k = i / fade
        rumble[i] = rumble[i] * k + raw[n + i] * (1 - k)

    out = []
    for i in range(n):
        t = i / RATE
        tone = sum(math.sin(2 * math.pi * base_hz * h * t) / h for h in range(1, harmonics + 1))
        # cylinders firing: periodic "chug" in the volume
        chug = 0.55 + 0.45 * abs(math.sin(math.pi * fire_hz * t)) ** 3
        out.append(tone * chug + noise_amount * rumble[i] * 4)
    return out


if __name__ == "__main__":
    rng = random.Random(42)  # same sounds every time
    save("fire.wav", fire(rng))
    save("explosion.wav", explosion(rng), peak=0.8)
    save("hit.wav", hit(rng), peak=0.9)
    save("pickup.wav", pickup(rng), peak=0.6)
    save("game_over.wav", game_over(rng), peak=0.6)
    save("engine_idle.wav", engine(rng, base_hz=30, fire_hz=10, harmonics=6, noise_amount=0.35), peak=0.7)
    save("engine_run.wav", engine(rng, base_hz=52, fire_hz=26, harmonics=9, noise_amount=0.5), peak=0.75)
