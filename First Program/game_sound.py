"""Sound effects for project.py (cannon fire, engine, explosions).

Uses pygame's mixer so the engine can keep looping while shots play on top.
If pygame or an audio device is missing, every function quietly does nothing
and the game runs without sound.
"""
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")

enabled = False
muted = False
_sounds = {}
_idle_channel = None
_run_channel = None

FIRE_VOLUME = 0.8
EXPLOSION_VOLUME = 0.7
HIT_VOLUME = 0.9
PICKUP_VOLUME = 0.6
GAME_OVER_VOLUME = 0.7


def init():
    """Load the sounds and start the (silent) engine loops. Call once after the window opens."""
    global enabled, _idle_channel, _run_channel
    try:
        import pygame
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(2)  # channels 0 and 1 belong to the engine
        for name in ("fire", "explosion", "hit", "pickup", "game_over", "engine_idle", "engine_run"):
            _sounds[name] = pygame.mixer.Sound(os.path.join(SOUND_DIR, name + ".wav"))
        _idle_channel = pygame.mixer.Channel(0)
        _run_channel = pygame.mixer.Channel(1)
        _idle_channel.play(_sounds["engine_idle"], loops=-1)
        _run_channel.play(_sounds["engine_run"], loops=-1)
        _idle_channel.set_volume(0)
        _run_channel.set_volume(0)
        enabled = True
    except Exception as e:  # no pygame, no sound card, missing files...
        print("Sound disabled:", e)
        enabled = False


def _play(name, volume):
    if not enabled or muted:
        return
    channel = _sounds[name].play()
    if channel is not None:
        channel.set_volume(volume)


def play_fire():
    _play("fire", FIRE_VOLUME)


def play_explosion():
    _play("explosion", EXPLOSION_VOLUME)


def play_hit():
    """The tank crashed into an alien and lost a life."""
    _play("hit", HIT_VOLUME)


def play_pickup():
    """A blue power-up ball was collected."""
    _play("pickup", PICKUP_VOLUME)


def play_game_over():
    _play("game_over", GAME_OVER_VOLUME)


def set_engine(speed_ratio, boosting=False):
    """Blend idle -> running engine by speed (0 = standing still, 1 = top speed)."""
    if not enabled:
        return
    if muted:
        _idle_channel.set_volume(0)
        _run_channel.set_volume(0)
        return
    r = max(0.0, min(1.0, speed_ratio))
    _idle_channel.set_volume(0.30 * (1 - r) + 0.06)
    _run_channel.set_volume(0.15 + 0.55 * r + (0.15 if boosting else 0.0) if r > 0.02 else 0.0)


def engine_off():
    if enabled:
        _idle_channel.set_volume(0)
        _run_channel.set_volume(0)


def pause():
    if enabled:
        import pygame
        pygame.mixer.pause()


def resume():
    if enabled:
        import pygame
        pygame.mixer.unpause()


def toggle_mute():
    global muted
    muted = not muted
    if muted:
        engine_off()
    return muted
