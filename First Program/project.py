import json
import math
import os
import random
import sys
import threading
import time
import urllib.request

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

import game_sound as sound  # cannon / engine / explosion effects (silent if pygame is missing)

# --- Website integration: set by the Flask backend when launched from the site ---
API_URL = os.environ.get("TANK_API_URL")
PLAYER_NAME = os.environ.get("TANK_PLAYER", "Player")
SESSION_ID = os.environ.get("TANK_SESSION_ID")
score_reported = False

def report_score(final_score, duration_seconds):
    """Send the final score to the backend in a background thread (no-op when run standalone)."""
    if not API_URL:
        return
    payload = json.dumps({
        "player_name": PLAYER_NAME,
        "score": int(final_score),
        "duration_seconds": int(duration_seconds),
        "session_id": SESSION_ID,
        "difficulty": DIFFICULTY,
    }).encode("utf-8")

    def send():
        try:
            req = urllib.request.Request(API_URL + "/api/scores", data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print("Could not report score:", e)

    threading.Thread(target=send, daemon=True).start()

# -----------------------
# Game state (kept & extended)
# -----------------------
bark_texture = None
game_start_time = time.time()
day_mode = 1
auto_day_night = True
car_x, car_z = 0.0, 0.0
car_angle = 0.0
current_speed = 0.0
max_speed = 15.0

acceleration = 0.05
deceleration = 0.5
brake_deceleration = 1.0
car_width = 1.5 * 0.9
car_length = 3.0 * 0.81
car_height = 1.2 * 0.81
steering_speed = 45.0
wheel_rotation_angle = 0.0
first_person_view = False
game_active = True
score = 0
time_of_day = 6 * 60
obstacles = []
powerups = []
next_obstacle_time = 0
game_over_time = 0
lives = 5

# Jump
car_jump_height = 0.0
car_jump_velocity = 0.0
is_jumping = False
jump_power = 3.75
gravity = 1.5


particles = []
enhanced_lighting = True
particle_count = 0

# Use the original Particle class from y.py
class Particle:
    def __init__(self, x, y, z, vx, vy, vz, life, color):
        self.x = x; self.y = y; self.z = z
        self.vx = vx; self.vy = vy; self.vz = vz
        self.life = life
        self.color = color
        self.age = 0.0

# particle helpers (from y.py)
def add_particles(x, y, z, count=12, spread=0.6, color=(1,0.6,0.2)):
    for _ in range(count):
        vx = random.uniform(-spread, spread)
        vy = random.uniform(0.2, spread*1.2)
        vz = random.uniform(-spread, spread)
        life = random.uniform(0.4, 1.0)
        particles.append(Particle(x, y, z, vx, vy, vz, life, color))

def update_particles(dt):
    for p in particles[:]:
        p.age += dt
        if p.age >= p.life:
            particles.remove(p)
            continue
        p.x += p.vx * dt * 10
        p.y += p.vy * dt * 10 - 9.8 * (p.age * 0.2)
        p.z += p.vz * dt * 10
        p.vy -= 9.8 * dt * 0.5

def draw_particles():
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glPointSize(4)
    glBegin(GL_POINTS)
    for p in particles:
        a = max(0.0, 1.0 - (p.age / p.life))
        glColor4f(p.color[0], p.color[1], p.color[2], 0.9 * a)
        glVertex3f(p.x, p.y, p.z)
    glEnd()
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_DEPTH_TEST)

def setup_enhanced_lighting():
    """Setup enhanced lighting system with multiple light sources"""
    global enhanced_lighting, day_mode

    if not enhanced_lighting:
        return

    # Enable lighting
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)
    glEnable(GL_LIGHT2)

    # Main directional light (sun)
    if day_mode == 1:  # Day
        glLightfv(GL_LIGHT0, GL_POSITION, [0.5, 1.0, 0.5, 0.0])  # Directional
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 0.9, 1.0])   # Warm white
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 0.9, 1.0])
    else:  # Bright Evening
        glLightfv(GL_LIGHT0, GL_POSITION, [0.4, 0.9, 0.4, 0.0])  # Higher angle for brightness
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 0.8, 0.5, 1.0])   # Brighter warm orange
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0, 0.8, 0.5, 1.0])


    glDisable(GL_LIGHT1)

    # Ambient lighting
    if day_mode == 1:  # Day
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
    else:  # Bright Evening
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.4, 0.35, 0.25, 1.0])  # Brighter ambient

camera_angle_horizontal = 0.0
camera_angle_vertical = 18.0
camera_distance = 9.0
car_height_offset = 3.2
camera_rotation_speed = 3.9
camera_vertical_speed = 2.0
min_vertical_angle = 3.0
max_vertical_angle = 85.0
camera_damping = 0.3  # Increased damping for more responsive camera
cam_target = [0.0, 0.0, 0.0]
camera_shake = 0.0

# Road / scene
road_width = 12
scene_start = -50
scene_end = 5000  # shorter for demo; you can increase
building_spacing = 40
tree_spacing = 30
view_dist = 200  # NEW: Visible range for optimization (ahead/behind car)
WINDOWS_PER_BUILDING = 4  # REDUCED: From 6 to 4 for fewer windows

# Procedural heights
building_heights = {}
tree_heights = {}

# Input state
keys = {
    b'w': False, b's': False, b'a': False, b'd': False, b' ': False, b'r': False, b'l': False,
    b'1': False, b'2': False, b'3': False, b'g': False, b'h': False, b'j': False, b'f': False,
    # b't': False, b'y': False, b'u': False,  # Weather controls - removed
    b'c': False,  # Mode switch (Day/Evening)
    b'p': False,  # Pause / resume
    b'm': False,  # Mute / unmute sound
    'left': False, 'right': False, 'up': False, 'down': False
}

# Particles
particles = []

# Bullets
bullets = []
bullet_speed = 120.0  # Much higher bullet speed for faster projectiles
max_bullets = 30  # More shells for enhanced gameplay
last_fire_time = 0.0
fire_rate = 0.15  # Minimum seconds between two shells
pending_shots = 0  # F presses / clicks waiting to fire (every press fires one shell)
MAX_PENDING_SHOTS = 10

# Pause (P or Esc)
paused = False
pause_started = 0.0
barrel_heat = 0.0  # Barrel heat system
max_barrel_heat = 100.0
barrel_cooldown_rate = 10.0  # Heat dissipation per second
recoil_force = 0.0  # Tank recoil effect
shell_type = 'armor_piercing'  # Only the most powerful shell
auto_aim_enabled = True  # Enhanced aiming system

# Difficulty (chosen on the website, passed in TANK_DIFFICULTY; defaults to medium)
DIFFICULTY_SETTINGS = {
    #          seconds between spawns, enemies per spawn, max on screen, speed multiplier, HUD color
    #          min_gap = smallest distance between two enemies when one spawns
    'easy':   {'spawn_interval': 5.0, 'per_spawn': 1, 'max_enemies': 6,  'speed_mult': 0.8,  'min_gap': 10.0, 'color': (0.3, 1.0, 0.4)},
    'medium': {'spawn_interval': 3.0, 'per_spawn': 1, 'max_enemies': 15, 'speed_mult': 1.0,  'min_gap': 8.0,  'color': (1.0, 0.8, 0.2)},
    'hard':   {'spawn_interval': 1.5, 'per_spawn': 2, 'max_enemies': 30, 'speed_mult': 1.25, 'min_gap': 7.0,  'color': (1.0, 0.3, 0.3)},
}
DIFFICULTY = os.environ.get("TANK_DIFFICULTY", "medium").lower()
if DIFFICULTY not in DIFFICULTY_SETTINGS:
    DIFFICULTY = 'medium'
difficulty = DIFFICULTY_SETTINGS[DIFFICULTY]

# Enemies
enemies = []
enemy_spawn_timer = 0.0
enemy_spawn_interval = difficulty['spawn_interval']
max_enemies = difficulty['max_enemies']

# Score system
score = 0

# HUD / gameplay
boost_meter = 0.0
boosting = False
boost_max = 5.0
boost_consumption = 0.05

# Misc tuning
OBSTACLE_Z_AHEAD = 140
SPAWN_DELAY = 2.0  # INCREASED: Slightly to reduce obstacle density
# ... (rest of globals unchanged)

# -----------------------
# Helper classes (unchanged)
# -----------------------
class Obstacle:
    def __init__(self, z_pos):
        # Only create blue powerups - no red or green obstacles
        self.kind = 'powerup'
        self.z = z_pos
        self.x = random.uniform(-road_width/2 + 1.2, road_width/2 - 1.2)
        # All obstacles are now blue powerups
        self.type = 'power'
        self.color = (0.2, 0.4, 1.0)  # Bright blue color
        self.pu = 'points'  # All powerups give points now
        self.scale = 0.5  # Smaller size
        self.scored = False
        self.hit = False
        self.hit_time = 0.0

class Particle:
    def __init__(self, x, y, z, vx, vy, vz, life, color):
        self.x = x; self.y = y; self.z = z
        self.vx = vx; self.vy = vy; self.vz = vz
        self.life = life
        self.color = color
        self.age = 0.0

class Bullet:
    def __init__(self, x, y, z, vx, vy, vz, shell_type='standard'):
        self.x = x
        self.y = y
        self.z = z
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.shell_type = shell_type
        self.age = 0.0
        self.trail = []  # Trail points for visual effect

        # Shell properties based on type
        if shell_type == 'standard':
            self.life = 8.0
            self.radius = 0.15
            self.color = (0.8, 0.6, 0.2)  # Brass
            self.gravity = 4.9
            self.drag = 0.995
            self.explosion_radius = 2.0
            self.damage = 15
        elif shell_type == 'armor_piercing':
            self.life = 10.0
            self.radius = 0.12  # Even smaller size for more realistic appearance
            self.color = (1.0, 0.0, 0.0)  # BRIGHT RED for maximum visibility
            self.gravity = 3.0
            self.drag = 0.998
            self.explosion_radius = 3.0  # Increased explosion radius for better area damage
            self.damage = 25
        elif shell_type == 'explosive':
            self.life = 6.0
            self.radius = 0.18
            self.color = (1.0, 0.4, 0.1)  # Orange
            self.gravity = 6.0
            self.drag = 0.99
            self.explosion_radius = 4.0
            self.damage = 20

class Enemy:
    def __init__(self, x, z):
        self.x = x
        self.y = 0.0
        self.z = z
        self.speed = 5.0 + random.random() * 2.5  # Moderate enemy speed: 5.0-7.5
        self.radius = 1.0
        self.health = 1
        self.color = (1.0, 0.2, 0.2)  # Red enemy
        self.pulse = 0.0  # For pulsing effect
        self.walk_cycle = 0.0  # For walking animation

# -----------------------
# Utility & drawing helpers (minor changes for state saving)
# -----------------------
def init():
    glClearColor(0.5, 0.8, 1.0, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_NORMALIZE)
    glShadeModel(GL_SMOOTH)
    glEnable(GL_COLOR_MATERIAL)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(60, 800/600, 1.0, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glDepthFunc(GL_LEQUAL)
    glEnable(GL_DEPTH_CLAMP)
    glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_NICEST)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH | GLUT_MULTISAMPLE)

def reset_game():
    # (unchanged)
    global car_x, car_z, car_angle, current_speed, camera_angle_horizontal, camera_angle_vertical
    global headlights_on, first_person_view, game_active, score, obstacles, particles, powerups, lives
    global game_start_time, next_obstacle_time, car_jump_height, car_jump_velocity, is_jumping, boost_meter, bullets
    global enemies, enemy_spawn_timer, barrel_heat, recoil_force, score_reported, pending_shots, paused
    score_reported = False
    pending_shots = 0
    paused = False
    sound.resume()
    game_start_time = time.time()
    obstacles = []
    powerups = []
    particles = []
    bullets = []
    enemies = []
    enemy_spawn_timer = 0.0
    next_obstacle_time = time.time() + 2.0
    car_x, car_z = 0.0, 0.0
    car_angle = 0.0
    current_speed = 0.0
    camera_angle_horizontal = 0.0
    camera_angle_vertical = 18.0
    headlights_on = False
    first_person_view = False
    game_active = True
    score = 0
    lives = 5
    car_jump_height = 0.0
    car_jump_velocity = 0.0
    is_jumping = False
    boost_meter = boost_max / 2
    barrel_heat = 0.0
    recoil_force = 0.0

def spawn_obstacle(z_offset=OBSTACLE_Z_AHEAD):
    z = car_z + z_offset + random.uniform(-10, 30)
    obs = Obstacle(z)
    obstacles.append(obs)

def spawn_powerup(z_offset=OBSTACLE_Z_AHEAD):
    z = car_z + z_offset + random.uniform(-20, 40)
    obs = Obstacle(z)
    obs.kind = 'powerup'
    obs.type = 'power'
    obstacles.append(obs)

# particle helpers (unchanged)
def add_particles(x, y, z, count=12, spread=0.6, color=(1,0.6,0.2)):
    for _ in range(count):
        vx = random.uniform(-spread, spread)
        vy = random.uniform(0.2, spread*1.2)
        vz = random.uniform(-spread, spread)
        life = random.uniform(0.4, 1.0)
        particles.append(Particle(x, y, z, vx, vy, vz, life, color))

def update_particles(dt):
    for p in particles[:]:
        p.age += dt
        if p.age >= p.life:
            particles.remove(p)
            continue
        p.x += p.vx * dt * 10
        p.y += p.vy * dt * 10 - 9.8 * (p.age * 0.2)
        p.z += p.vz * dt * 10
        p.vy -= 9.8 * dt * 0.5

def draw_particles():
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glPointSize(4)
    glBegin(GL_POINTS)
    for p in particles:
        a = max(0.0, 1.0 - (p.age / p.life))
        glColor4f(p.color[0], p.color[1], p.color[2], 0.9 * a)
        glVertex3f(p.x, p.y, p.z)
    glEnd()
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_DEPTH_TEST)

# Bullet helper functions
def fire_bullet():
    global bullets, barrel_heat, recoil_force
    if len(bullets) >= max_bullets:
        return  # Limit number of shells


    tank_center_x = car_x
    tank_center_y = car_height/2 + car_jump_height
    tank_center_z = car_z

    # Gun muzzle position relative to tank center (EXACT match with draw_tank_gun)
    # From draw_tank_gun: glTranslatef(0, 0.6, 2.6) - this is the muzzle position
    gun_local_x = 0.0
    gun_local_y = 0.6  # Height above tank center (matches draw_tank_gun)
    gun_local_z = 2.6  # Forward from tank center (matches draw_tank_gun muzzle)

    # Apply EXACT same rotation as draw_car: glRotatef(car_angle, 0, 1, 0)
    # This is a Y-axis rotation (around vertical axis)
    angle_rad = math.radians(car_angle)
    cos_angle = math.cos(angle_rad)
    sin_angle = math.sin(angle_rad)

    # Transform gun position using EXACT same math as OpenGL rotation
    # For Y-axis rotation: x' = x*cos - z*sin, y' = y, z' = x*sin + z*cos
    gun_x = tank_center_x + gun_local_x * cos_angle - gun_local_z * sin_angle
    gun_y = tank_center_y + gun_local_y  # Y doesn't change in Y-axis rotation
    gun_z = tank_center_z + gun_local_x * sin_angle + gun_local_z * cos_angle

    # Calculate shell direction (forward from tank) - PRECISE direction
    # The shell should travel in the same direction the tank is facing
    # Shell speed is much higher for faster projectiles
    shell_speed = max(current_speed * 2.0, bullet_speed)  # Use bullet_speed as minimum

    # Calculate tank's current movement velocity components
    tank_vx = current_speed * sin_angle  # Tank's X velocity
    tank_vz = current_speed * cos_angle  # Tank's Z velocity

    # Shell velocity = shell speed in tank's direction + tank's current velocity
    # This ensures shells maintain proper trajectory even when tank is moving sideways
    shell_vx = shell_speed * sin_angle + tank_vx * 0.3  # Add some tank momentum
    shell_vy = 0.0  # No initial vertical velocity (horizontal firing)
    shell_vz = shell_speed * cos_angle + tank_vz * 0.3  # Add some tank momentum

    # Use the powerful armor piercing shell
    shell_type = 'armor_piercing'

    # Create new shell with PRECISE position and velocity
    shell = Bullet(gun_x, gun_y, gun_z, shell_vx, shell_vy, shell_vz, shell_type)
    bullets.append(shell)
    sound.play_fire()

    # Add barrel heat for armor piercing shell
    barrel_heat += 20.0

    # Add recoil force
    recoil_force = 0.3

    # Add dramatic muzzle flash effect for tank firing (at EXACT muzzle position)
    flash_color = (0.8, 0.8, 0.9)  # Steel gray flash for armor piercing
    add_particles(gun_x, gun_y, gun_z, count=30, spread=0.8, color=flash_color)  # More particles for visibility
    add_particles(gun_x, gun_y, gun_z, count=20, spread=0.4, color=(1.0, 1.0, 0.8))  # Brighter flash
    add_particles(gun_x, gun_y, gun_z, count=15, spread=0.2, color=(1.0, 0.0, 0.0))  # RED flash for barrel tip - VERY VISIBLE

    # Add camera shake for tank firing
    global camera_shake
    shake_intensity = 0.3  # Moderate shake for armor piercing
    camera_shake = shake_intensity

def create_shell_explosion(x, y, z, shell_type='standard'):
    """Create a dramatic shell explosion effect based on shell type"""
    global camera_shake

    if shell_type == 'standard':
        # Standard explosion
        add_particles(x, y, z, count=25, spread=2.0, color=(1.0, 0.6, 0.1))  # Orange fire
        add_particles(x, y, z, count=15, spread=1.5, color=(1.0, 1.0, 0.3))  # Yellow flash
        add_particles(x, y, z, count=10, spread=1.0, color=(0.8, 0.8, 0.8))  # Gray smoke
        camera_shake = 0.6
    elif shell_type == 'armor_piercing':
        # Armor piercing - smaller but intense
        add_particles(x, y, z, count=15, spread=1.0, color=(0.9, 0.9, 1.0))  # White flash
        add_particles(x, y, z, count=8, spread=0.8, color=(0.6, 0.6, 0.7))   # Steel sparks
        add_particles(x, y, z, count=5, spread=0.5, color=(0.8, 0.8, 0.8))   # Gray smoke
        camera_shake = 0.4
    elif shell_type == 'explosive':
        # Explosive - massive explosion
        add_particles(x, y, z, count=40, spread=3.0, color=(1.0, 0.4, 0.1))  # Orange fire
        add_particles(x, y, z, count=25, spread=2.5, color=(1.0, 0.8, 0.2))  # Yellow flash
        add_particles(x, y, z, count=20, spread=2.0, color=(0.6, 0.6, 0.6))  # Gray smoke
        add_particles(x, y, z, count=15, spread=1.5, color=(0.8, 0.2, 0.1))  # Red sparks
        camera_shake = 1.0

    # Ground impact crater effect
    crater_size = 1.2 if shell_type == 'standard' else 0.8 if shell_type == 'armor_piercing' else 2.0
    add_particles(x, 0.1, z, count=12, spread=crater_size, color=(0.4, 0.3, 0.2))  # Brown dirt

def update_bullets(dt):
    global bullets, enemies, score
    for bullet in bullets[:]:
        try:
            bullet.age += dt
            if bullet.age >= bullet.life:
                # Shell explodes when lifetime expires
                explosion_x = bullet.x
                explosion_y = bullet.y
                explosion_z = bullet.z

                create_shell_explosion(explosion_x, explosion_y, explosion_z, bullet.shell_type)

                # Damage all enemies within explosion radius
                for enemy in enemies[:]:
                    # Calculate distance from explosion center to enemy
                    enemy_center_y = 0.8
                    explosion_distance = math.sqrt((explosion_x - enemy.x)**2 + (explosion_y - enemy_center_y)**2 + (explosion_z - enemy.z)**2)

                    # Check if enemy is within explosion radius
                    if explosion_distance <= bullet.explosion_radius:
                        # Apply damage to enemy
                        enemy.health -= bullet.damage

                        # Check if enemy is dead
                        if enemy.health <= 0:
                            enemies.remove(enemy)
                            score += 15  # +15 points for killing enemy
                            sound.play_explosion()

                            # Add extra particles for enemy death
                            add_particles(enemy.x, enemy_center_y, enemy.z, count=20, spread=1.5, color=(1.0, 0.8, 0.2))
                        else:
                            # Enemy damaged but not dead - add damage indicator
                            add_particles(enemy.x, enemy_center_y, enemy.z, count=8, spread=0.8, color=(1.0, 0.4, 0.4))

                bullets.remove(bullet)
                continue

            # Add current position to trail (keep last 10 points)
            bullet.trail.append((bullet.x, bullet.y, bullet.z))
            if len(bullet.trail) > 10:
                bullet.trail.pop(0)

            # Update shell position with ballistic physics
            bullet.prev = (bullet.x, bullet.y, bullet.z)  # for swept collision checks
            bullet.x += bullet.vx * dt
            bullet.y += bullet.vy * dt
            bullet.z += bullet.vz * dt

            # Apply gravity to shell (realistic ballistic trajectory)
            bullet.vy -= bullet.gravity * dt

            # Apply air resistance/drag
            bullet.vx *= bullet.drag
            bullet.vy *= bullet.drag
            bullet.vz *= bullet.drag

            # Check for ground impact
            if bullet.y <= 0.1:  # Shell hits ground
                # Create explosion at ground impact
                explosion_x = bullet.x
                explosion_y = 0.1
                explosion_z = bullet.z

                create_shell_explosion(explosion_x, explosion_y, explosion_z, bullet.shell_type)

                # Damage all enemies within explosion radius
                for enemy in enemies[:]:
                    # Calculate distance from explosion center to enemy
                    enemy_center_y = 0.8
                    explosion_distance = math.sqrt((explosion_x - enemy.x)**2 + (explosion_y - enemy_center_y)**2 + (explosion_z - enemy.z)**2)

                    # Check if enemy is within explosion radius
                    if explosion_distance <= bullet.explosion_radius:
                        # Apply damage to enemy
                        enemy.health -= bullet.damage

                        # Check if enemy is dead
                        if enemy.health <= 0:
                            enemies.remove(enemy)
                            score += 15  # +15 points for killing enemy
                            sound.play_explosion()

                            # Add extra particles for enemy death
                            add_particles(enemy.x, enemy_center_y, enemy.z, count=20, spread=1.5, color=(1.0, 0.8, 0.2))
                        else:
                            # Enemy damaged but not dead - add damage indicator
                            add_particles(enemy.x, enemy_center_y, enemy.z, count=8, spread=0.8, color=(1.0, 0.4, 0.4))

                bullets.remove(bullet)
                continue

            # Remove shells that are too far away (with safety checks) - increased range
            if (abs(bullet.x) > 500 or bullet.y < -30 or
                abs(bullet.z - car_z) > 600):
                bullets.remove(bullet)
        except (AttributeError, ValueError) as e:
            # Remove corrupted shells
            bullets.remove(bullet)
            continue

def draw_bullets():
    if not bullets:  # Skip if no shells
        return

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    for bullet in bullets:
        try:
            # Draw shell trail first (behind the shell)
            if len(bullet.trail) > 1:
                glLineWidth(3.0)
                glBegin(GL_LINE_STRIP)
                for i, (tx, ty, tz) in enumerate(bullet.trail):
                    # Fade trail based on age, use shell's color
                    alpha = (i / len(bullet.trail)) * 0.6
                    glColor4f(*bullet.color, alpha)
                    glVertex3f(tx, ty, tz)
                glEnd()
                glLineWidth(1.0)

            # Draw the shell itself
            glPushMatrix()
            glTranslatef(bullet.x, bullet.y, bullet.z)

            # Shell body - use shell's actual color (armor piercing = steel gray)
            glColor4f(*bullet.color, 0.95)
            glutSolidSphere(bullet.radius, 12, 12)

            # Shell tip - darker version of shell color
            tip_color = (bullet.color[0] * 0.7, bullet.color[1] * 0.7, bullet.color[2] * 0.7)
            glColor4f(*tip_color, 0.95)
            glTranslatef(0, 0, bullet.radius * 0.3)
            glutSolidSphere(bullet.radius * 0.4, 8, 8)
            glTranslatef(0, 0, -bullet.radius * 0.3)

            # Add a bright glow effect for visibility - ENHANCED
            glow_color = (1.0, 1.0, 1.0)  # BRIGHT WHITE GLOW for maximum visibility
            glColor4f(*glow_color, 0.8)  # More opaque glow
            glutSolidSphere(bullet.radius * 2.5, 8, 8)  # Much larger glow

            glPopMatrix()
        except (AttributeError, ValueError) as e:
            # Skip corrupted shells
            glPopMatrix()
            continue

    glDisable(GL_BLEND)

def spawn_enemy():
    global enemies, enemy_spawn_timer
    if len(enemies) >= max_enemies:
        return

    for _ in range(difficulty['per_spawn']):
        if len(enemies) >= max_enemies:
            break
        # Spawn ahead of the car, but never on top of another enemy (keeps a gap to shoot through)
        for _attempt in range(12):
            spawn_x = (random.random() - 0.5) * 8.0  # Random position across road width
            spawn_z = car_z + 50.0 + random.random() * 50.0  # 50-100 units ahead
            if all(math.hypot(spawn_x - e.x, spawn_z - e.z) >= difficulty['min_gap'] for e in enemies):
                break
        else:
            continue  # road ahead is full; try again on the next spawn tick

        enemy = Enemy(spawn_x, spawn_z)
        enemy.speed *= difficulty['speed_mult']
        enemies.append(enemy)

def update_enemies(dt):
    global enemies, score, lives, game_active, game_over_time
    for enemy in enemies[:]:
        # Move enemy towards car
        enemy.z -= enemy.speed * dt
        enemy.pulse += dt * 5.0  # Pulsing effect
        enemy.walk_cycle += dt * 8.0  # Walking animation cycle

        # Remove enemies that are behind the car
        if enemy.z < car_z - 20:
            enemies.remove(enemy)
            continue

        # Check collision with car
        distance_to_car = math.sqrt((enemy.x - car_x)**2 + (enemy.z - car_z)**2)
        if distance_to_car < (enemy.radius + 1.2):  # Tank radius ~1.2
            # Check if car is jumping high enough to clear the enemy
            car_height_above_ground = car_jump_height
            enemy_height = 1.6  # Approximate height of humanoid enemy (head to feet)

            if is_jumping and car_height_above_ground > enemy_height * 0.7:  # Need to clear 70% of enemy height
                # Successfully jumped over enemy - no penalty, enemy continues
                continue
            else:
                # Car collision with enemy (not jumping or not high enough)
                lives -= 1
                enemies.remove(enemy)
                sound.play_hit()
                # Check for game over
                if lives <= 0:
                    game_active = False
                    game_over_time = time.time()
                    sound.play_game_over()
                continue

def draw_enemies():
    glEnable(GL_DEPTH_TEST)
    for enemy in enemies:
        glPushMatrix()
        glTranslatef(enemy.x, enemy.y, enemy.z)

        # Pulsing effect for intimidation
        pulse_scale = 1.0 + 0.1 * math.sin(enemy.pulse)
        glScalef(pulse_scale, pulse_scale, pulse_scale)

        # Enemy color with pulsing intensity
        intensity = 0.8 + 0.2 * math.sin(enemy.pulse)
        glColor3f(enemy.color[0] * intensity, enemy.color[1] * intensity, enemy.color[2] * intensity)

        # Walking animation - slight bobbing
        walk_bob = 0.1 * math.sin(enemy.walk_cycle)
        glTranslatef(0, walk_bob, 0)

        # Rotate enemy to face forward (towards the car)
        glRotatef(180, 0, 1, 0)  # Rotate 180 degrees around Y-axis

        # Draw humanoid enemy

        # HEAD (red sphere)
        glPushMatrix()
        glTranslatef(0, 1.2, 0)
        glutSolidSphere(0.3, 8, 8)

        # EYES (white spheres with black pupils)
        glColor3f(1.0, 1.0, 1.0)  # White eyes
        glPushMatrix()
        glTranslatef(-0.1, 0.1, 0.25)
        glutSolidSphere(0.08, 6, 6)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0.1, 0.1, 0.25)
        glutSolidSphere(0.08, 6, 6)
        glPopMatrix()

        # BLACK PUPILS
        glColor3f(0.0, 0.0, 0.0)  # Black pupils
        glPushMatrix()
        glTranslatef(-0.1, 0.1, 0.3)
        glutSolidSphere(0.04, 6, 6)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0.1, 0.1, 0.3)
        glutSolidSphere(0.04, 6, 6)
        glPopMatrix()

        glPopMatrix()

        # BODY (red cube) - wider to connect with arms
        glColor3f(enemy.color[0] * intensity, enemy.color[1] * intensity, enemy.color[2] * intensity)
        glPushMatrix()
        glTranslatef(0, 0.6, 0)
        glScalef(0.8, 0.8, 0.4)  # Increased width from 0.6 to 0.8
        glutSolidCube(1)
        glPopMatrix()

        # ARMS (red cylinders) - positioned to connect with body
        arm_swing = 0.3 * math.sin(enemy.walk_cycle)
        glPushMatrix()
        glTranslatef(-0.4, 0.7, 0)  # Positioned at body edge for seamless connection
        glRotatef(arm_swing * 30, 1, 0, 0)  # Arm swinging
        glRotatef(90, 0, 1, 0)
        glutSolidCylinder(0.1, 0.6, 6, 6)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(0.4, 0.7, 0)  # Positioned at body edge for seamless connection
        glRotatef(-arm_swing * 30, 1, 0, 0)  # Opposite arm swinging
        glRotatef(90, 0, 1, 0)
        glutSolidCylinder(0.1, 0.6, 6, 6)
        glPopMatrix()

        # LEFT HAND (from user's perspective) - make it HIGHLY visible
        glPushMatrix()
        glTranslatef(-0.4 - 0.6, 0.7, 0)  # Left hand at end of left arm (user's left)
        glColor3f(1.0, 0.0, 0.0)  # Bright red for maximum visibility
        glutSolidSphere(0.2, 12, 12)  # Much larger sphere for better visibility
        glPopMatrix()

        # RIGHT HAND (from user's perspective) - make it HIGHLY visible
        glPushMatrix()
        glTranslatef(0.4 + 0.6, 0.7, 0)  # Right hand at end of right arm (user's right)
        glColor3f(1.0, 0.0, 0.0)  # Bright red for maximum visibility
        glutSolidSphere(0.2, 12, 12)  # Much larger sphere for better visibility
        glPopMatrix()

        # SMALL CYLINDERS on LEFT hand (from user's perspective) - connected to body
        glPushMatrix()
        glTranslatef(-0.4 - 0.6, 0.7, 0)  # Position at left hand (user's left)
        glColor3f(0.9, 0.0, 0.0)  # Bright red for cylinder
        glRotatef(90, 0, 1, 0)  # Rotate to extend horizontally
        glutSolidCylinder(0.08, 0.5, 12, 12)  # Larger cylinder for better visibility
        glPopMatrix()

        # Restore enemy color for remaining parts
        glColor3f(enemy.color[0] * intensity, enemy.color[1] * intensity, enemy.color[2] * intensity)

        # LEGS (red cylinders with walking animation)
        leg_swing = 0.4 * math.sin(enemy.walk_cycle)
        glPushMatrix()
        glTranslatef(-0.2, 0.2, 0)
        glRotatef(leg_swing * 20, 1, 0, 0)  # Leg swinging
        glRotatef(90, 1, 0, 0)
        glutSolidCylinder(0.12, 0.8, 6, 6)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(0.2, 0.2, 0)
        glRotatef(-leg_swing * 20, 1, 0, 0)  # Opposite leg swinging
        glRotatef(90, 1, 0, 0)
        glutSolidCylinder(0.12, 0.8, 6, 6)
        glPopMatrix()

        # FEET (dark red spheres)
        glColor3f(0.6, 0.1, 0.1)  # Darker red for feet
        glPushMatrix()
        glTranslatef(-0.2, -0.2, 0.8 * math.sin(leg_swing * 0.3))
        glutSolidSphere(0.15, 6, 6)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0.2, -0.2, 0.8 * math.sin(-leg_swing * 0.3))
        glutSolidSphere(0.15, 6, 6)
        glPopMatrix()

        glPopMatrix()

def segment_point_distance(a, b, p):
    """Shortest distance from point p to the line segment a-b (3D)."""
    abx, aby, abz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    apx, apy, apz = p[0] - a[0], p[1] - a[1], p[2] - a[2]
    length_sq = abx * abx + aby * aby + abz * abz
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, (apx * abx + apy * aby + apz * abz) / length_sq))
    cx, cy, cz = a[0] + abx * t - p[0], a[1] + aby * t - p[1], a[2] + abz * t - p[2]
    return math.sqrt(cx * cx + cy * cy + cz * cz)

def check_bullet_enemy_collisions():
    global bullets, enemies, score, camera_shake
    for bullet in bullets[:]:
        for enemy in enemies[:]:
            # ULTRA-PRECISE COLLISION DETECTION - Works even when tank is moving
            # Calculate distance between bullet and enemy (use enemy center height)
            enemy_center_y = 0.8  # Enemy center height

            # Shells move several units per frame, so test the whole path travelled
            # this frame (prev -> current), not just the end point; otherwise they pass through
            distance = segment_point_distance(getattr(bullet, 'prev', (bullet.x, bullet.y, bullet.z)),
                                              (bullet.x, bullet.y, bullet.z),
                                              (enemy.x, enemy_center_y, enemy.z))

            # ULTRA-PRECISE collision threshold - very generous for moving tank scenarios
            # Use bullet radius + enemy radius + generous tolerance for moving tank
            collision_threshold = bullet.radius + enemy.radius + 0.8  # Increased tolerance for moving tank

            # Primary collision detection - very generous for moving tank
            if distance < collision_threshold:
                # HIT DETECTED - immediate kill
                bullets.remove(bullet)
                enemies.remove(enemy)
                score += 15  # +15 points for direct kill
                sound.play_explosion()

                # Add explosion effect for direct hit
                create_shell_explosion(bullet.x, bullet.y, bullet.z, bullet.shell_type)

                # Add dramatic death particles (more visible)
                add_particles(enemy.x, enemy_center_y, enemy.z, count=40, spread=2.5, color=(1.0, 0.8, 0.2))  # Golden explosion
                add_particles(enemy.x, enemy_center_y, enemy.z, count=20, spread=2.0, color=(1.0, 0.2, 0.2))  # Red blood effect
                add_particles(enemy.x, enemy_center_y, enemy.z, count=15, spread=1.5, color=(0.8, 0.8, 0.8))  # Smoke effect

                # Add camera shake for enemy kill
                camera_shake = 0.3  # More intense shake
                break

# -----------------------
# Drawing: sky, ground, scenery, car, obstacles, HUD (optimized)
# -----------------------
def draw_sky():
    # (unchanged)
    t = (time_of_day % (24*60)) / (24*60)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glBegin(GL_QUADS)
    if day_mode == 1:
        top = (0.2, 0.6, 1.0)
        bottom = (0.7, 0.9, 1.0)
    else:  # Evening
        top = (0.12, 0.1, 0.25)
        bottom = (0.9, 0.5, 0.3)
    glColor3f(*top); glVertex3f(-200, 200, -200)
    glColor3f(*top); glVertex3f(200, 200, -200)
    glColor3f(*bottom); glVertex3f(200, -10, -200)
    glColor3f(*bottom); glVertex3f(-200, -10, -200)
    glEnd()
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()

    # Sun and moon removed as requested

# Sun and moon removed as requested

def draw_ground():
    # big ground (unchanged)
    if day_mode == 1:
        ground_col = (0.2, 0.6, 0.25)
    else:  # Bright Evening
        ground_col = (0.25, 0.5, 0.2)  # Brighter green for evening

    glColor3f(*ground_col)
    glBegin(GL_QUADS)
    glVertex3f(-200, 0, scene_start)
    glVertex3f(-200, 0, scene_end)
    glVertex3f(200, 0, scene_end)
    glVertex3f(200, 0, scene_start)
    glEnd()

    # road base (unchanged)
    road_y = 0.02
    if day_mode == 1:
        road_col = (0.18, 0.18, 0.18)
    else:  # Bright Evening
        road_col = (0.22, 0.22, 0.22)  # Brighter road for evening
    glColor3f(*road_col)
    glBegin(GL_QUADS)
    glVertex3f(-road_width / 2, road_y, scene_start)
    glVertex3f(-road_width / 2, road_y, scene_end)
    glVertex3f(road_width / 2, road_y, scene_end)
    glVertex3f(road_width / 2, road_y, scene_start)
    glEnd()

    # reflective highlight (unchanged)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    highlight = 0.06 if day_mode==1 else 0.08  # Brighter highlight for evening
    glColor4f(1.0, 1.0, 1.0, highlight)
    glBegin(GL_QUADS)
    glVertex3f(-road_width/2 + 0.5, road_y+0.001, scene_start)
    glVertex3f(-road_width/2 + 0.5, road_y+0.001, scene_end)
    glVertex3f(road_width/2 - 0.5, road_y+0.001, scene_end)
    glVertex3f(road_width/2 - 0.5, road_y+0.001, scene_start)
    glEnd()
    glDisable(GL_BLEND)  # FIXED: Disable here to avoid leak

    # lane marks (OPTIMIZED: Limit to visible range)
    lane_width = 0.25
    lane_length = 1.8
    gap_length = 4.0
    cycle_length = lane_length + gap_length
    mark_col = (1,1,1) if day_mode==1 else (0.9,0.9,0.9)  # Brighter lane markings for evening

    # Compute visible range
    z_start = max(scene_start, car_z - view_dist)
    z_end = min(scene_end, car_z + view_dist / 2)  # Less ahead since camera looks forward

    # Align start z to dash pattern
    start_offset = z_start % cycle_length
    z = z_start - start_offset + (gap_length if start_offset < lane_length else 0)

    glColor3f(*mark_col)
    while z < z_end:
        if z + lane_length > z_start:  # Only draw if intersects visible range
            glBegin(GL_QUADS)
            glVertex3f(-lane_width/2, road_y + 0.02, max(z, z_start))
            glVertex3f(-lane_width/2, road_y + 0.02, min(z + lane_length, z_end))
            glVertex3f(lane_width/2, road_y + 0.02, min(z + lane_length, z_end))
            glVertex3f(lane_width/2, road_y + 0.02, max(z, z_start))
            glEnd()
        z += cycle_length

# Persistent states for buildings (unchanged)
building_states = {}
def draw_building(x, z, scale_x, scale_y, scale_z, base_color):
    """Enhanced building drawing function with improved architecture and details
    NOTE: No gate/entrance functions - buildings are solid structures without doors"""
    global building_states

    key = (x, z)  # unique ID for each building

    if key not in building_states:
        # ----------------------------
        # INITIALIZE BUILDING STATE
        # ----------------------------
        state = {}

        # Enhanced facade colors with more variety
        facade_colors = [
            (0.85, 0.75, 0.65),  # warm beige
            (0.7, 0.8, 0.9),     # light blue
            (0.8, 0.7, 0.6),     # tan
            (0.75, 0.85, 0.8),   # mint
            (0.9, 0.8, 0.7),     # cream
            (0.65, 0.7, 0.85),   # lavender
            (0.8, 0.6, 0.5),     # terracotta
            (0.7, 0.9, 0.8),     # sage green
            (0.85, 0.7, 0.8),    # rose
            (0.6, 0.8, 0.9)      # sky blue
]

        chosen = random.choice(facade_colors)
        state["color"] = (
            chosen[0] * random.uniform(0.85, 1.15),
            chosen[1] * random.uniform(0.85, 1.15),
            chosen[2] * random.uniform(0.85, 1.15)
        )

        # Simplified window configuration - fixed structure
        windows = []
        num_rows = 4  # Fixed number of rows for simplicity
        num_cols = 5  # Fixed number of columns (matches window positions)
        for r in range(num_rows):
            row_states = []
            for c in range(num_cols):
                # More realistic window lighting pattern
                lit_prob = 0.4 if r < num_rows // 2 else 0.6  # Lower floors more likely to be lit
                row_states.append(random.random() > lit_prob)
            windows.append(row_states)
        state["windows"] = windows

        # Building type for architectural variety
        state["building_type"] = random.choice(["modern", "classic", "office", "residential"])

        # Roof style
        state["roof_style"] = random.choice(["flat", "sloped", "domed"])

        building_states[key] = state

    # Retrieve persistent state
    state = building_states[key]
    col = state["color"]
    windows = state["windows"]
    building_type = state["building_type"]
    roof_style = state["roof_style"]

    # Debug: ensure col is a tuple
    if not isinstance(col, (tuple, list)) or len(col) != 3:
        col = (0.7, 0.7, 0.7)  # Default gray color

    glPushMatrix()
    glTranslatef(x, 0, z)  # Position building with bottom at ground level (Y=0)

    # Save/restore all attributes
    glPushAttrib(GL_ALL_ATTRIB_BITS)
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LESS)
    glEnable(GL_CULL_FACE)

    # ----------------------------
    # APPLY TIME OF DAY COLOR ADJUSTMENTS
    # ----------------------------
    if day_mode == 2:  # bright evening
        col = tuple(c * 0.9 for c in col)  # Less darkening for brighter evening

    # ----------------------------
    # PROPER MULTI-STORY BUILDING
    # ----------------------------
    # Calculate number of floors based on building height
    num_floors = max(3, int(scale_y / 3.0))  # Each floor is about 3 units high
    floor_height = 2.8  # Fixed floor height for consistency
    total_building_height = num_floors * floor_height

    # Draw each floor as a distinct building section
    for floor in range(num_floors):
        floor_y = (floor * floor_height) + floor_height/2  # Position floors from bottom up

        # Each floor has slightly different color to distinguish them
        floor_col = (
            col[0] * (0.85 + floor * 0.05),
            col[1] * (0.85 + floor * 0.05),
            col[2] * (0.85 + floor * 0.05)
        )

        # Draw the floor as a complete building section
        glColor3f(*floor_col)
        glPushMatrix()
        glTranslatef(0, floor_y, 0)
        glScalef(scale_x, floor_height, scale_z)
        glutSolidCube(1)
        glPopMatrix()

        # Add floor separator (thicker, more visible)
        if floor < num_floors - 1:  # Don't draw separator after top floor
            separator_y = -total_building_height/2 + ((floor + 1) * floor_height)
            glColor3f(col[0] * 0.4, col[1] * 0.4, col[2] * 0.4)  # Darker separator
            glBegin(GL_QUADS)
            # Thicker separator line
            glVertex3f(-scale_x/2, separator_y - 0.1, 0.501)
            glVertex3f(scale_x/2, separator_y - 0.1, 0.501)
            glVertex3f(scale_x/2, separator_y + 0.1, 0.501)
            glVertex3f(-scale_x/2, separator_y + 0.1, 0.501)
            glEnd()

            # Add side separators for more definition
            glColor3f(col[0] * 0.3, col[1] * 0.3, col[2] * 0.3)
            # Left side separator
            glBegin(GL_QUADS)
            glVertex3f(-scale_x/2 - 0.05, separator_y - 0.1, 0.501)
            glVertex3f(-scale_x/2 + 0.05, separator_y - 0.1, 0.501)
            glVertex3f(-scale_x/2 + 0.05, separator_y + 0.1, 0.501)
            glVertex3f(-scale_x/2 - 0.05, separator_y + 0.1, 0.501)
            glEnd()
            # Right side separator
            glBegin(GL_QUADS)
            glVertex3f(scale_x/2 - 0.05, separator_y - 0.1, 0.501)
            glVertex3f(scale_x/2 + 0.05, separator_y - 0.1, 0.501)
            glVertex3f(scale_x/2 + 0.05, separator_y + 0.1, 0.501)
            glVertex3f(scale_x/2 - 0.05, separator_y + 0.1, 0.501)
            glEnd()

    # ----------------------------
    # ARCHITECTURAL DETAILS
    # ----------------------------

    # Building facade lines (horizontal)
    glColor3f(col[0] * 0.7, col[1] * 0.7, col[2] * 0.7)
    glBegin(GL_LINES)
    for i in range(-int(scale_y/2), int(scale_y/2) + 1):
        y_pos = i * 0.2
        if abs(y_pos) < scale_y - 0.1:  # Don't draw lines at edges
            glVertex3f(-0.5, y_pos, 0.501)
            glVertex3f(0.5, y_pos, 0.501)
    glEnd()

    # Vertical facade lines
    glBegin(GL_LINES)
    for i in range(-3, 4):
        x_pos = i * 0.15
        if abs(x_pos) < 0.45:
            glVertex3f(x_pos, 0.1, 0.501)
            glVertex3f(x_pos, scale_y - 0.1, 0.501)
    glEnd()

    # ----------------------------
    # WINDOWS ON EACH FLOOR
    # ----------------------------
    # Disable depth testing temporarily to ensure windows are always visible
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_CULL_FACE)

    # Different window colors for variety
    window_colors = [
        (0.5, 0.8, 1.0),   # Sky blue
        (1.0, 1.0, 0.0),   # Yellow
        (0.8, 0.9, 1.0),   # Light blue
        (1.0, 0.9, 0.5),   # Light yellow
        (0.7, 0.9, 1.0),   # Pale blue
        (1.0, 0.8, 0.3),   # Golden yellow
        (0.6, 0.8, 1.0),   # Soft blue
        (1.0, 0.7, 0.0),   # Orange yellow
        (0.8, 0.8, 1.0),   # Lavender blue
    ]

    # Add windows to each floor
    for floor in range(num_floors):
        floor_y = (floor * floor_height) + floor_height/2  # Position floors from bottom up

        # Windows aligned with building partitions (5 windows per floor)
        window_x_positions = [-0.3, -0.15, 0.0, 0.15, 0.3]

        for window_idx, x_pos in enumerate(window_x_positions):
            y_pos = floor_y

            # Window frame - dark gray
            glColor3f(0.3, 0.3, 0.3)  # Dark gray frame
            glBegin(GL_QUADS)
            glVertex3f(x_pos - 0.08, y_pos - 0.08, 0.51)
            glVertex3f(x_pos + 0.08, y_pos - 0.08, 0.51)
            glVertex3f(x_pos + 0.08, y_pos + 0.08, 0.51)
            glVertex3f(x_pos - 0.08, y_pos + 0.08, 0.51)
            glEnd()

            # Window glass - colorful based on time of day
            if day_mode == 2:  # bright evening
                # At bright evening, use warm colors
                glColor3f(1.0, 0.8, 0.4)  # Brighter warm orange
            else:  # day
                # During day, use different colors for each floor
                color_idx = (floor * 5 + window_idx) % len(window_colors)
                glColor3f(*window_colors[color_idx])

            glBegin(GL_QUADS)
            glVertex3f(x_pos - 0.06, y_pos - 0.06, 0.52)
            glVertex3f(x_pos + 0.06, y_pos - 0.06, 0.52)
            glVertex3f(x_pos + 0.06, y_pos + 0.06, 0.52)
            glVertex3f(x_pos - 0.06, y_pos + 0.06, 0.52)
            glEnd()

    # Re-enable depth testing and culling
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_CULL_FACE)


    # ----------------------------
    # ENHANCED ROOF
    # ----------------------------
    if roof_style == "flat":
        # Flat roof with ledge
        glColor3f(col[0] * 0.6, col[1] * 0.6, col[2] * 0.6)
        glBegin(GL_QUADS)
        glVertex3f(-0.5, scale_y, 0.51)
        glVertex3f(0.5, scale_y, 0.51)
        glVertex3f(0.5, scale_y + 0.08, 0.51)
        glVertex3f(-0.5, scale_y + 0.08, 0.51)
        glEnd()

        # Roof ledge
        glColor3f(col[0] * 0.4, col[1] * 0.4, col[2] * 0.4)
        glBegin(GL_QUADS)
        glVertex3f(-0.52, scale_y + 0.08, 0.49)
        glVertex3f(0.52, scale_y + 0.08, 0.49)
        glVertex3f(0.52, scale_y + 0.08, 0.53)
        glVertex3f(-0.52, scale_y + 0.08, 0.53)
        glEnd()

    elif roof_style == "sloped":
        # Sloped roof
        glColor3f(col[0] * 0.5, col[1] * 0.5, col[2] * 0.5)
        glBegin(GL_TRIANGLES)
        glVertex3f(0, scale_y + 0.3, 0.51)
        glVertex3f(-0.5, scale_y, 0.51)
        glVertex3f(0.5, scale_y, 0.51)
        glEnd()

    elif roof_style == "domed":
        # Domed roof
        glColor3f(col[0] * 0.6, col[1] * 0.6, col[2] * 0.6)
        glPushMatrix()
        glTranslatef(0, scale_y + 0.2, 0.51)  # Position roof at top of building
        glutSolidSphere(0.3, 12, 8)
        glPopMatrix()

    # ----------------------------
    # BUILDING BASE
    # ----------------------------
    glColor3f(col[0] * 0.3, col[1] * 0.3, col[2] * 0.3)
    glBegin(GL_QUADS)
    glVertex3f(-0.5, -0.5, 0.501)
    glVertex3f(0.5, -0.5, 0.501)
    glVertex3f(0.5, -0.48, 0.501)
    glVertex3f(-0.5, -0.48, 0.501)
    glEnd()

    # ----------------------------
    # SIDE FACES - SIMPLIFIED (removed for now to focus on front face)
    # ----------------------------

    glPopAttrib()
    glDisable(GL_CULL_FACE)
    glPopMatrix()


def draw_tree(x, z, trunk_height, leaf_radius):
    glPushMatrix()
    glTranslatef(x, 0, z)  # Position at base of tree

    # Save/restore attributes
    glPushAttrib(GL_ALL_ATTRIB_BITS)
    glEnable(GL_POLYGON_OFFSET_FILL)
    glPolygonOffset(1.0, 1.0)
    glEnable(GL_LIGHTING)  # Enable lighting for better shading
    glEnable(GL_LIGHT0)    # Use light for realism

    # Random seed for consistent variation
    random.seed(hash((x, z)))

    # Slight height and size variation
    height_variation = 1.0 + (random.random() - 0.5) * 0.15
    trunk_height *= height_variation
    leaf_radius *= height_variation * 1.3

    # ------------------------------
    # Trunk with bark details
    # ------------------------------
    if day_mode == 1:
        trunk_color = [0.55, 0.35, 0.15]  # Light brown (day)
        bark_accent = [0.45, 0.25, 0.1]   # Darker brown for texture
    else:
        trunk_color = [0.5, 0.3, 0.15]  # Brighter brown for evening
        bark_accent = [0.4, 0.2, 0.1]  # Brighter for evening

    # Tapered trunk (cone for natural shape)
    glPushMatrix()
    glTranslatef(0, trunk_height * 0.5, 0)
    glRotatef(-90, 1, 0, 0)  # Align cone vertically
    glColor3f(*trunk_color)
    glutSolidCone(0.4, trunk_height, 12, 4)  # Base radius 0.4, height=trunk_height
    glPopMatrix()

    # Bark texture (vertical lines)
    glColor3f(*bark_accent)
    glBegin(GL_LINES)
    for i in range(8):
        angle = i * 45 * 3.14159 / 180.0
        x_offset = 0.38 * math.cos(angle)
        z_offset = 0.38 * math.sin(angle)
        glVertex3f(x_offset, 0.0, z_offset)
        glVertex3f(x_offset * 0.8, trunk_height * 0.8, z_offset * 0.8)
    glEnd()

    # ------------------------------
    # Root system (organic extensions)
    # ------------------------------
    for i in range(4):  # Four roots for fuller base
        glPushMatrix()
        angle = i * 90 * 3.14159 / 180.0
        glTranslatef(0.5 * math.cos(angle), 0.1, 0.5 * math.sin(angle))
        glRotatef(45, math.sin(angle), 0, -math.cos(angle))  # Slight curve outward
        glScalef(0.3, 0.4, 0.3)
        glColor3f(*bark_accent)
        glutSolidCone(0.3, 0.8, 8, 2)  # Smaller, shorter cones for roots
        glPopMatrix()

    # ------------------------------
    # Foliage with layered canopy
    # ------------------------------
    glTranslatef(0, trunk_height * 0.7, 0)  # Move up to canopy base

    if day_mode == 1:
        base_color = [0.2, 0.7, 0.15]  # Vibrant green (day)
        leaf_colors = [
            [0.25, 0.75, 0.2],  # Bright green
            [0.2, 0.65, 0.15],  # Mid green
            [0.3, 0.8, 0.25]    # Light green
        ]
    else:
        base_color = [0.25, 0.6, 0.15]  # Brighter green for evening
        leaf_colors = [
            [0.3, 0.65, 0.2],  # Brighter green
            [0.15, 0.45, 0.1],  # Mid dark
            [0.2, 0.55, 0.15]   # Slightly lighter
        ]

    # Enable blending for subtle leaf transparency
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # Main canopy (larger base sphere)
    glColor4f(base_color[0], base_color[1], base_color[2], 0.95)
    glutSolidSphere(leaf_radius * 0.9, 16, 16)

    # Layered leaf clusters (8 clusters across 2 layers)
    num_clusters = 8
    for layer in range(2):  # Two layers for depth
        layer_height = layer * leaf_radius * 0.5
        layer_scale = 0.7 - layer * 0.2  # Smaller clusters higher up
        for i in range(num_clusters):
            glPushMatrix()
            angle = (i + layer * 0.5) * 2 * 3.14159 / num_clusters  # Stagger angles
            radius_offset = leaf_radius * (0.6 + random.random() * 0.4)
            height_offset = layer_height + random.random() * leaf_radius * 0.3
            glTranslatef(radius_offset * math.cos(angle), height_offset, radius_offset * math.sin(angle))
            glColor4f(leaf_colors[random.randint(0, 2)][0], leaf_colors[random.randint(0, 2)][1],
                      leaf_colors[random.randint(0, 2)][2], 0.85)
            glutSolidSphere(leaf_radius * layer_scale * 0.35, 10, 10)
            glPopMatrix()

    # ------------------------------
    # Ground shadow (simple circle)
    # ------------------------------
    glDisable(GL_LIGHTING)
    glColor4f(0.1, 0.1, 0.1, 0.3)  # Semi-transparent dark shadow
    glPushMatrix()
    glTranslatef(0, 0.01, 0)  # Slightly above ground to avoid z-fighting
    glBegin(GL_TRIANGLE_FAN)
    glVertex3f(0, 0, 0)
    for i in range(13):
        angle = i * 2 * 3.14159 / 12
        glVertex3f(leaf_radius * 0.9 * math.cos(angle), 0, leaf_radius * 0.9 * math.sin(angle))
    glEnd()
    glPopMatrix()

    glDisable(GL_BLEND)
    glPopAttrib()
    glPopMatrix()

def draw_grass(x, z, grass_height=0.3, grass_width=0.1):
    """Draw pointed grass at specified position"""
    glPushMatrix()
    glTranslatef(x, 0, z)

    # Grass color based on time of day
    if day_mode == 1:
        grass_col = (0.3, 0.7, 0.2)  # Bright green during day
    else:  # Bright Evening
        grass_col = (0.25, 0.6, 0.18)  # Brighter green for evening

    glColor3f(*grass_col)

    # Draw multiple grass blades in a small area
    for i in range(3):
        glPushMatrix()
        # Random offset for each blade
        offset_x = (random.random() - 0.5) * grass_width
        offset_z = (random.random() - 0.5) * grass_width
        glTranslatef(offset_x, 0, offset_z)

        # Draw pointed grass blade as a triangle
        glBegin(GL_TRIANGLES)
        glVertex3f(0, 0, 0)  # Base
        glVertex3f(-grass_width/3, grass_height, 0)  # Left point
        glVertex3f(grass_width/3, grass_height, 0)   # Right point
        glEnd()

        glPopMatrix()

    glPopMatrix()

def draw_scenery():
    global building_heights
    z_start = max(scene_start, car_z - view_dist)
    z_end = min(scene_end, car_z + view_dist)

    # -----------------------
    # LEFT SIDE BUILDINGS
    # -----------------------
    current_z = (int(z_start // building_spacing) * building_spacing)
    while current_z < z_end:
        # Use a unique key for left side buildings by adding "left" prefix
        key = f"left_{current_z}"
        if key not in building_heights:
            building_heights[key] = random.uniform(8, 15)
        height1 = building_heights[key]

        # Second building with its own unique key
        key2 = f"left2_{current_z}"
        if key2 not in building_heights:
            building_heights[key2] = random.uniform(6, 12)
        height2 = building_heights[key2]

        # Multiple buildings left of the road
        draw_building(-road_width/2 - 6, current_z, 4, height1, 3, (0.7, 0.7, 0.8))
        draw_building(-road_width/2 - 12, current_z, 3.5, height2, 3, (0.6, 0.8, 0.7))

        current_z += building_spacing

    # -----------------------
    # RIGHT SIDE BUILDINGS
    # -----------------------
    current_z = (int((z_start + building_spacing//2) // building_spacing) * building_spacing)
    while current_z < z_end:
        # Use a unique key for right side buildings by adding "right" prefix
        key = f"right_{current_z}"
        if key not in building_heights:
            building_heights[key] = random.uniform(8, 15)
        height1 = building_heights[key]

        # Second building with its own unique key
        key2 = f"right2_{current_z}"
        if key2 not in building_heights:
            building_heights[key2] = random.uniform(6, 12)
        height2 = building_heights[key2]

        # Multiple buildings right of the road
        draw_building(road_width/2 + 6, current_z, 4, height1, 3, (0.7, 0.7, 0.8))
        draw_building(road_width/2 + 12, current_z, 3.5, height2, 3, (0.8, 0.7, 0.6))

        current_z += building_spacing

    # -----------------------
    # SMALL TREES BETWEEN BUILDINGS
    # -----------------------
    # Add small trees between buildings on both sides
    tree_z_start = (int(z_start // building_spacing) * building_spacing) + building_spacing // 2
    while tree_z_start < z_end:
        # Left side small trees
        draw_small_tree(-road_width/2 - 3, tree_z_start)
        draw_small_tree(-road_width/2 - 9, tree_z_start)
        draw_small_tree(-road_width/2 - 15, tree_z_start)

        # Right side small trees
        draw_small_tree(road_width/2 + 3, tree_z_start)
        draw_small_tree(road_width/2 + 9, tree_z_start)
        draw_small_tree(road_width/2 + 15, tree_z_start)

        tree_z_start += building_spacing

def draw_small_tree(x, z, tree_height=2.5):
    """Draw a small tree between buildings"""
    glPushMatrix()
    glTranslatef(x, 0, z)

    # Tree trunk - smaller and darker
    if day_mode == 1:
        trunk_color = [0.4, 0.25, 0.1]  # Darker brown for small tree
    else:
        trunk_color = [0.35, 0.2, 0.08]  # Even darker for evening

    glColor3f(*trunk_color)
    glPushMatrix()
    glTranslatef(0, tree_height * 0.3, 0)
    glRotatef(-90, 1, 0, 0)
    glutSolidCylinder(0.08, tree_height * 0.6, 8, 4)  # Smaller trunk
    glPopMatrix()

    # Tree foliage - smaller and more compact
    if day_mode == 1:
        foliage_color = [0.15, 0.5, 0.1]  # Darker green for small tree
    else:
        foliage_color = [0.2, 0.45, 0.12]  # Brighter for evening

    glColor3f(*foliage_color)
    glPushMatrix()
    glTranslatef(0, tree_height * 0.7, 0)
    glutSolidSphere(tree_height * 0.3, 8, 6)  # Smaller foliage sphere
    glPopMatrix()

    glPopMatrix()

# (draw_car, draw_enhanced_car_body, draw_windows, draw_wheels, draw_lights, draw_obstacle, draw_minimap, draw_speedometer_and_hud, draw_text - unchanged)


def draw_car():
    glPushMatrix()
    glTranslatef(car_x, car_height/2 + car_jump_height, car_z)
    glRotatef(car_angle, 0, 1, 0)

    # Draw army tank
    draw_tank()

    glPopMatrix()

def draw_tank():
    # Save attributes to avoid state leaks
    glPushAttrib(GL_ALL_ATTRIB_BITS)

    # Draw tank body
    draw_tank_body()

    # Draw tank tracks
    draw_tank_tracks()

    # Draw tank turret
    draw_tank_turret()

    # Draw main gun barrel at front
    draw_tank_gun()

    glPopAttrib()

def draw_tank_body():
    # Main tank body - military green color
    glColor3f(0.3, 0.4, 0.2)  # Military green

    # Main hull - INCREASED LENGTH
    glPushMatrix()
    glScalef(2.2, 0.8, 2.5)  # Wide, low, LONGER tank body (increased from 1.8 to 2.5)
    glutSolidCube(1)
    glPopMatrix()

    # Front armor plate (angled) - ADJUSTED FOR LONGER TANK
    glColor3f(0.25, 0.35, 0.15)  # Darker green
    glPushMatrix()
    glTranslatef(0, 0, 0.8)  # Move to front (adjusted for longer tank)
    glRotatef(15, 1, 0, 0)  # Angled front
    glScalef(2.0, 0.6, 0.3)  # Angled front plate
    glutSolidCube(1)
    glPopMatrix()

    # Side armor plates - ADJUSTED FOR LONGER TANK
    glColor3f(0.28, 0.38, 0.18)  # Slightly different green
    # Left side
    glPushMatrix()
    glTranslatef(-1.0, 0, 0)
    glScalef(0.2, 0.6, 2.2)  # Increased length to match longer tank
    glutSolidCube(1)
    glPopMatrix()
    # Right side
    glPushMatrix()
    glTranslatef(1.0, 0, 0)
    glScalef(0.2, 0.6, 2.2)  # Increased length to match longer tank
    glutSolidCube(1)
    glPopMatrix()

def draw_tank_tracks():
    # Tank tracks - dark gray/black
    glColor3f(0.15, 0.15, 0.15)  # Dark gray tracks

    # Left track - ADJUSTED FOR LONGER TANK
    glPushMatrix()
    glTranslatef(-1.1, -0.3, 0)
    glScalef(0.3, 0.4, 2.4)  # Longer track to match tank length
    glutSolidCube(1)
    glPopMatrix()

    # Right track - ADJUSTED FOR LONGER TANK
    glPushMatrix()
    glTranslatef(1.1, -0.3, 0)
    glScalef(0.3, 0.4, 2.4)  # Longer track to match tank length
    glutSolidCube(1)
    glPopMatrix()

    # Track details - road wheels - MORE WHEELS FOR LONGER TANK
    glColor3f(0.2, 0.2, 0.2)  # Slightly lighter for wheels
    wheel_positions = [-1.0, -0.6, -0.2, 0.2, 0.6, 1.0]  # 6 wheels per side for longer tank

    for pos in wheel_positions:
        # Left wheelsmm


        glPushMatrix()
        glTranslatef(-1.1, -0.3, pos)
        glutSolidCylinder(0.15, 0.25, 12, 4)
        glPopMatrix()

        # Right wheels
        glPushMatrix()
        glTranslatef(1.1, -0.3, pos)
        glutSolidCylinder(0.15, 0.25, 12, 4)
        glPopMatrix()

def draw_tank_turret():
    # Tank turret - dark gray/black
    glColor3f(0.2, 0.2, 0.2)  # Dark gray for turret

    # Main turret body
    glPushMatrix()
    glTranslatef(0, 0.6, 0)  # Position above hull
    glScalef(1.4, 0.6, 1.2)  # Rounded turret
    glutSolidCube(1)
    glPopMatrix()

    # Turret top (slightly domed)
    glColor3f(0.3, 0.4, 0.2)  # Darker green
    glPushMatrix()
    glTranslatef(0, 0.9, 0)
    glScalef(1.2, 0.3, 1.0)
    glutSolidCube(1)
    glPopMatrix()

    # Commander's hatch
    glColor3f(0.2, 0.2, 0.2)  # Dark gray hatch
    glPushMatrix()
    glTranslatef(0, 1.0, 0)
    glScalef(0.4, 0.1, 0.6)
    glutSolidCube(1)
    glPopMatrix()

def draw_tank_gun():
    # Main gun barrel - HORIZONTAL and PROPERLY CONNECTED to tank
    glColor3f(0.2, 0.2, 0.2)  # Dark gray gun

    # Gun mount (where barrel attaches to turret) - CONNECTED TO TURRET
    glPushMatrix()
    glTranslatef(0, 0.6, 0.6)  # Position at front of turret (no gap)
    glScalef(0.4, 0.3, 0.4)  # Gun mount - slightly longer for better connection
    glutSolidCube(1)
    glPopMatrix()

    # Main gun barrel - HORIZONTAL cylinder extending forward from mount
    glColor3f(0.15, 0.15, 0.15)  # Darker gray barrel
    glPushMatrix()
    glTranslatef(0, 0.6, 0.8)  # Start from mount (no gap)
    # NO ROTATION - cylinder is already horizontal by default
    glutSolidCylinder(0.08, 1.8, 12, 8)  # Longer barrel (1.8 units)
    glPopMatrix()

    # Gun muzzle brake (end of barrel) - AT THE VERY FRONT
    glColor3f(0.25, 0.25, 0.25)  # Lighter gray muzzle
    glPushMatrix()
    glTranslatef(0, 0.6, 2.6)  # At end of barrel (adjusted for longer barrel)
    glScalef(0.15, 0.15, 0.1)
    glutSolidCube(1)
    glPopMatrix()

    # Gun sight
    glColor3f(0.3, 0.3, 0.3)  # Light gray sight
    glPushMatrix()
    glTranslatef(0.2, 0.7, 0.3)  # Position on turret
    glScalef(0.1, 0.1, 0.2)
    glutSolidCube(1)
    glPopMatrix()

def draw_enhanced_car_body():
    # Sports car design with purple and magenta theme
    glColor3f(0.5, 0.2, 0.8)  # Purple main body

    # Main car body - sleeker design
    glPushMatrix()
    glScalef(car_width, car_height * 0.8, car_length * 1.2)  # Lower and longer
    glutSolidCube(1)
    glPopMatrix()

    # Front section - more pointed (darker purple)
    glColor3f(0.4, 0.15, 0.7)  # Darker purple for front
    glPushMatrix()
    glTranslatef(0, 0, car_length * 0.4)
    glScalef(car_width * 0.7, car_height * 0.6, car_length * 0.3)
    glutSolidCube(1)
    glPopMatrix()

    # Rear section - wider and more angular (magenta)
    glColor3f(0.8, 0.2, 0.6)  # Magenta rear section
    glPushMatrix()
    glTranslatef(0, 0, -car_length * 0.4)
    glScalef(car_width * 1.1, car_height * 0.7, car_length * 0.4)
    glutSolidCube(1)
    glPopMatrix()

    # Front bumper (dark purple)
    glColor3f(0.3, 0.1, 0.5)  # Dark purple bumper
    glPushMatrix()
    glTranslatef(0, -car_height/2 - 0.1, car_length/2 + 0.2)
    glScalef(car_width*0.6, 0.1, 0.3)
    glutSolidCube(1)
    glPopMatrix()

    # Rear bumper (dark magenta)
    glColor3f(0.6, 0.1, 0.4)  # Dark magenta bumper
    glPushMatrix()
    glTranslatef(0, -car_height/2 - 0.1, -car_length/2 - 0.2)
    glScalef(car_width*0.9, 0.1, 0.3)
    glutSolidCube(1)
    glPopMatrix()

    # Side skirts (magenta)
    glColor3f(0.7, 0.15, 0.5)  # Magenta side skirts
    glPushMatrix()
    glTranslatef(car_width/2 + 0.05, -car_height/2 - 0.05, 0)
    glScalef(0.1, 0.2, car_length * 0.8)
    glutSolidCube(1)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(-car_width/2 - 0.05, -car_height/2 - 0.05, 0)
    glScalef(0.1, 0.2, car_length * 0.8)
    glutSolidCube(1)
    glPopMatrix()

    # Add magenta accents on the hood
    glColor3f(0.8, 0.3, 0.7)  # Bright magenta hood accent
    glPushMatrix()
    glTranslatef(0, car_height/4, car_length/3)
    glScalef(car_width*0.8, 0.05, car_length*0.3)
    glutSolidCube(1)
    glPopMatrix()

def draw_windows():
    # Dark grey/black windows like in the image
    glColor3f(0.2, 0.2, 0.2)  # Dark grey windows
    glBegin(GL_QUADS)
    # front window
    glVertex3f(-car_width/2 * 0.8, -car_height/6, car_length/2 - 0.01)
    glVertex3f(-car_width/2 * 0.8, car_height/3, car_length/2 - 0.01)
    glVertex3f(car_width/2 * 0.8, car_height/3, car_length/2 - 0.01)
    glVertex3f(car_width/2 * 0.8, -car_height/6, car_length/2 - 0.01)
    # rear window
    glVertex3f(-car_width/2 * 0.8, -car_height/6, -car_length/2 + 0.01)
    glVertex3f(-car_width/2 * 0.8, car_height/3, -car_length/2 + 0.01)
    glVertex3f(car_width/2 * 0.8, car_height/3, -car_length/2 + 0.01)
    glVertex3f(car_width/2 * 0.8, -car_height/6, -car_length/2 + 0.01)
    # side windows
    glVertex3f(-car_width/2 - 0.01, -car_height/6, car_length/4)
    glVertex3f(-car_width/2 - 0.01, car_height/3, car_length/4)
    glVertex3f(-car_width/2 - 0.01, car_height/3, -car_length/4)
    glVertex3f(-car_width/2 - 0.01, -car_height/6, -car_length/4)
    glVertex3f(car_width/2 + 0.01, -car_height/6, car_length/4)
    glVertex3f(car_width/2 + 0.01, car_height/3, car_length/4)
    glVertex3f(car_width/2 + 0.01, car_height/3, -car_length/4)
    glVertex3f(car_width/2 + 0.01, -car_height/6, -car_length/4)
    glEnd()

def draw_wheels():
    global wheel_rotation_angle
    wheel_radius = 0.4
    wheel_width = 0.2
    # Position wheels closer to car body to eliminate gaps
    wheel_offset_x = car_width/2 + 0.1  # Close to car edge with small gap
    wheel_offset_z = car_length/2 - 0.3  # Slightly inset from car edges

    wheel_rotation_angle += current_speed * 1.2
    if wheel_rotation_angle > 360: wheel_rotation_angle -= 360

    positions = [
        (wheel_offset_x, wheel_offset_z),   # Front right
        (wheel_offset_x, -wheel_offset_z),  # Rear right
        (-wheel_offset_x, wheel_offset_z),  # Front left
        (-wheel_offset_x, -wheel_offset_z), # Rear left
    ]
    for x, z in positions:
        glPushMatrix()
        glTranslatef(x, -0.5 + wheel_radius, z)
        glRotatef(90, 0, 1, 0)
        glRotatef(wheel_rotation_angle, 0, 0, 1)

        # Black tire
        glColor3f(0.1, 0.1, 0.1)
        try:
            glutSolidCylinder(wheel_radius, wheel_width, 12, 6)
        except Exception:
            glutSolidTorus(0.1, wheel_radius, 8, 16)

        # White spokes/hubcap
        glColor3f(0.9, 0.9, 0.9)
        glutSolidTorus(0.05, wheel_radius - 0.1, 6, 12)

        # Small green center detail like in the image
        glColor3f(0.2, 0.8, 0.2)
        glutSolidSphere(0.05, 6, 6)

        glPopMatrix()

# def draw_lights():
#     """Headlights and lights function - REMOVED (no headlights on tank)"""
#     # All headlight and light functionality removed for tank
#     pass

def draw_obstacle(o):
    glPushMatrix()
    glTranslatef(o.x, 0.4 + 0.2, o.z)  # All obstacles are powerups now
    glColor3f(*o.color)
    # All obstacles are now blue powerups
    # spin sphere to signal power-up
    glRotatef((time.time()*60)%360, 0, 1, 0)
    glutSolidSphere(o.scale, 12, 12)  # Round sphere shape
    glPopMatrix()

# -----------------------
# HUD and on-screen buttons (2D overlay on a virtual 800x600 screen)
# -----------------------
HUD_W, HUD_H = 800, 600

def begin_2d():
    """Flat 2D drawing on top of the 3D scene. Lighting must be off or text renders black."""
    glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_COLOR_BUFFER_BIT)
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_FOG)
    glDisable(GL_CULL_FACE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, HUD_W, 0, HUD_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

def end_2d():
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopAttrib()

def text_width(text, font=GLUT_BITMAP_HELVETICA_12):
    return sum(glutBitmapWidth(font, ord(ch)) for ch in text)

def put_text(x, y, text, font=GLUT_BITMAP_HELVETICA_12, color=(1, 1, 1)):
    """Draw text; only call between begin_2d() and end_2d()."""
    glColor3f(*color)
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

def put_text_centered(cx, y, text, font=GLUT_BITMAP_HELVETICA_12, color=(1, 1, 1)):
    put_text(cx - text_width(text, font) / 2, y, text, font, color)

def fill_rect(x, y, w, h, color, alpha=1.0):
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glVertex2f(x, y); glVertex2f(x + w, y); glVertex2f(x + w, y + h); glVertex2f(x, y + h)
    glEnd()

def outline_rect(x, y, w, h, color, alpha=1.0):
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x, y); glVertex2f(x + w, y); glVertex2f(x + w, y + h); glVertex2f(x, y + h)
    glEnd()

def draw_key_button(x, y, w, h, label, caption=None, pressed=False):
    """A keyboard-style button; lights up while its key is pressed."""
    if pressed:
        fill_rect(x, y, w, h, (1.0, 0.75, 0.2), 0.95)
        label_color = (0.1, 0.1, 0.1)
    else:
        fill_rect(x, y, w, h, (0.12, 0.14, 0.18), 0.85)
        label_color = (1, 1, 1)
    outline_rect(x, y, w, h, (0.9, 0.9, 0.9), 0.9)
    font = GLUT_BITMAP_HELVETICA_18 if len(label) == 1 else GLUT_BITMAP_HELVETICA_12
    put_text_centered(x + w / 2, y + h / 2 - (6 if len(label) == 1 else 4), label, font, label_color)
    if caption:
        put_text_centered(x + w / 2, y - 13, caption, GLUT_BITMAP_HELVETICA_10, (0.9, 0.9, 0.9))

def draw_controls_panel():
    fill_rect(6, 6, 788, 92, (0.05, 0.06, 0.08), 0.55)

    # Drive cluster (W A S D)
    draw_key_button(46, 58, 30, 26, "W", None, keys[b'w'])
    draw_key_button(12, 28, 30, 26, "A", None, keys[b'a'])
    draw_key_button(46, 28, 30, 26, "S", None, keys[b's'])
    draw_key_button(80, 28, 30, 26, "D", None, keys[b'd'])
    put_text_centered(61, 13, "Drive / Steer", GLUT_BITMAP_HELVETICA_10, (0.9, 0.9, 0.9))

    # Camera cluster (arrow keys)
    draw_key_button(160, 58, 30, 26, "^", None, keys['up'])
    draw_key_button(126, 28, 30, 26, "<", None, keys['left'])
    draw_key_button(160, 28, 30, 26, "v", None, keys['down'])
    draw_key_button(194, 28, 30, 26, ">", None, keys['right'])
    put_text_centered(175, 13, "Camera", GLUT_BITMAP_HELVETICA_10, (0.9, 0.9, 0.9))

    # Action buttons
    actions = [
        ("SPACE", "Brake", b' '),
        ("J", "Jump", b'j'),
        ("F", "Fire / Click", b'f'),
        ("1", "Boost", b'1'),
        ("G", "1st View", b'g'),
        ("H", "3rd View", b'h'),
        ("C", "Day/Night", b'c'),
        ("R", "Restart", b'r'),
        ("P", "Pause", b'p'),
        ("M", "Unmute" if sound.muted else "Sound", b'm'),
    ]
    x = 244
    for label, caption, key in actions:
        w = 50 if len(label) > 1 else 38
        lit = keys[key] or (key == b'p' and paused) or (key == b'm' and sound.muted)
        draw_key_button(x + (53 - w) / 2, 40, w, 32, label, caption, lit)
        x += 55

def draw_status_panels():
    # Top-left: score, difficulty, lives, time
    fill_rect(8, 512, 196, 80, (0.05, 0.06, 0.08), 0.55)
    put_text(18, 568, f"Score: {score}", GLUT_BITMAP_HELVETICA_18, (1, 0.9, 0.3))
    put_text(196 - text_width(DIFFICULTY.upper()), 570, DIFFICULTY.upper(), GLUT_BITMAP_HELVETICA_12, difficulty['color'])
    put_text(18, 545, "Lives:", GLUT_BITMAP_HELVETICA_12)
    for i in range(5):
        alive = i < lives
        fill_rect(62 + i * 18, 543, 13, 12, (0.95, 0.25, 0.25) if alive else (0.3, 0.3, 0.3), 0.95)
    put_text(18, 522, f"Time: {int(time_of_day//60):02d}:{int(time_of_day%60):02d}   "
                      f"{['Day', 'Evening'][day_mode-1]} ({'auto' if auto_day_night else 'manual'})",
             GLUT_BITMAP_HELVETICA_10)

    # Top-right: speed, boost, shells
    speed_kmh = abs(current_speed) * 3.6
    fill_rect(592, 512, 200, 80, (0.05, 0.06, 0.08), 0.55)
    put_text(602, 570, f"Speed: {speed_kmh:.0f} km/h", GLUT_BITMAP_HELVETICA_12)
    put_text(602, 550, "Boost", GLUT_BITMAP_HELVETICA_12)
    fill_rect(645, 549, 135, 10, (0.25, 0.25, 0.25), 0.9)
    fill_rect(645, 549, 135 * max(0.0, min(1.0, boost_meter / boost_max)), 10, (0.0, 0.8, 1.0), 0.95)
    ready = (time.time() - last_fire_time) >= fire_rate and len(bullets) < max_bullets
    put_text(602, 530, f"Shells: {len(bullets)}/{max_bullets}", GLUT_BITMAP_HELVETICA_12)
    put_text(700, 530, "READY" if ready else "Reloading",
             GLUT_BITMAP_HELVETICA_12, (0.3, 1, 0.4) if ready else (1, 0.6, 0.2))
    if is_jumping:
        put_text(602, 516, "JUMPING!", GLUT_BITMAP_HELVETICA_10, (1, 0.9, 0.3))

def draw_start_hint():
    """Short help in the first seconds of a run."""
    if time.time() - game_start_time > 6:
        return
    fill_rect(220, 300, 360, 56, (0.05, 0.06, 0.08), 0.6)
    put_text_centered(400, 334, "Press W to drive, A / D to steer", GLUT_BITMAP_HELVETICA_18)
    put_text_centered(400, 312, "F or Left Click to fire  -  J to jump  -  P pause  -  M sound", GLUT_BITMAP_HELVETICA_12, (0.9, 0.9, 0.9))

def draw_speedometer_and_hud():
    begin_2d()
    draw_status_panels()
    draw_controls_panel()
    if game_active and not paused:
        draw_start_hint()
    end_2d()

def draw_paused():
    begin_2d()
    fill_rect(0, 0, HUD_W, HUD_H, (0.05, 0.05, 0.1), 0.55)
    fill_rect(250, 230, 300, 190, (0.08, 0.09, 0.12), 0.92)
    outline_rect(250, 230, 300, 190, (0.9, 0.9, 0.9), 0.6)
    put_text_centered(400, 385, "PAUSED", GLUT_BITMAP_TIMES_ROMAN_24, (0.4, 0.8, 1.0))
    put_text_centered(400, 355, f"Score: {score}", GLUT_BITMAP_HELVETICA_18, (1, 0.9, 0.3))
    draw_key_button(290, 298, 40, 30, "P", None, False)
    put_text(342, 306, "Resume  (or Esc)", GLUT_BITMAP_HELVETICA_18)
    draw_key_button(290, 254, 40, 30, "R", None, False)
    put_text(342, 262, "Restart", GLUT_BITMAP_HELVETICA_18)
    end_2d()

def draw_game_over():
    begin_2d()
    fill_rect(0, 0, HUD_W, HUD_H, (0.05, 0.05, 0.1), 0.6)
    fill_rect(230, 220, 340, 210, (0.08, 0.09, 0.12), 0.9)
    outline_rect(230, 220, 340, 210, (0.9, 0.9, 0.9), 0.6)
    put_text_centered(400, 395, "GAME OVER!", GLUT_BITMAP_TIMES_ROMAN_24, (1, 0.35, 0.35))
    put_text_centered(400, 355, f"Final Score: {score}", GLUT_BITMAP_HELVETICA_18, (1, 0.9, 0.3))
    put_text_centered(400, 330, "All Lives Lost!", GLUT_BITMAP_HELVETICA_12)
    draw_key_button(300, 268, 44, 32, "R", None, keys[b'r'])
    put_text(356, 278, "Press R to Restart", GLUT_BITMAP_HELVETICA_18)
    put_text_centered(400, 240, "Or wait 5 seconds for auto-restart", GLUT_BITMAP_HELVETICA_12, (0.8, 0.8, 0.8))
    end_2d()

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_12):
    begin_2d()
    put_text(x, y, text, font)
    end_2d()

def draw_centered_text(y, text, font=GLUT_BITMAP_HELVETICA_12):
    """Draw text centered horizontally on the screen (800px wide)"""
    begin_2d()
    put_text_centered(HUD_W / 2, y, text, font)
    end_2d()

# -----------------------
# Display and update loop (minor: Enable offset once)
# -----------------------
last_time = time.time()
def display():
    global time_of_day, day_mode, auto_day_night
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    # time progression (unchanged)
    if game_active and not paused:
        time_of_day += 0.5
        if time_of_day >= 24*60: time_of_day -= 24*60

    # determine mode and background color (day and bright evening only)
    if auto_day_night:
        # Automatic day/night cycling based on time
        if 6*60 <= time_of_day < 18*60:
            # Day mode (6 AM to 6 PM)
            r,g,b = (0.5, 0.8, 1.0); day_mode = 1
        else:
            # Bright evening mode (6 PM to 6 AM)
            r,g,b = (0.9, 0.7, 0.4); day_mode = 2  # Brighter evening colors
    else:
        # Manual mode - use current day_mode setting
        if day_mode == 1:
            r,g,b = (0.5, 0.8, 1.0)  # Day colors
        else:
            r,g,b = (0.9, 0.7, 0.4)  # Evening colors

    # headlights_on = False  # Removed - no headlights on tank

    # Set clear color for background
    glClearColor(r, g, b, 1.0)

    # camera (unchanged)
    if first_person_view:
        eye_x = car_x + 0.35 * math.sin(math.radians(car_angle))
        eye_y = car_height * 0.75 + car_jump_height
        eye_z = car_z + 0.35 * math.cos(math.radians(car_angle))
        look_x = car_x + math.sin(math.radians(car_angle))*2
        look_y = eye_y - 0.15
        look_z = car_z + math.cos(math.radians(car_angle))*2
        gluLookAt(eye_x, eye_y, eye_z, look_x, look_y, look_z, 0, 1, 0)
    else:
        # smoother third-person camera with damping
        global cam_target
        desired_cam_x = car_x - camera_distance * math.sin(math.radians(car_angle + camera_angle_horizontal)) * math.cos(math.radians(camera_angle_vertical))
        desired_cam_y = car_height_offset + camera_distance * math.sin(math.radians(camera_angle_vertical))
        desired_cam_z = car_z - camera_distance * math.cos(math.radians(car_angle + camera_angle_horizontal)) * math.cos(math.radians(camera_angle_vertical))
        cam_target[0] += (desired_cam_x - cam_target[0]) * camera_damping
        cam_target[1] += (desired_cam_y - cam_target[1]) * camera_damping
        cam_target[2] += (desired_cam_z - cam_target[2]) * camera_damping
        gluLookAt(cam_target[0], cam_target[1] + camera_shake, cam_target[2], car_x, car_height/2 + car_jump_height, car_z, 0, 1, 0)

    # sky - draw after camera is set up to prevent camera rotation from affecting sky
    draw_sky()

    # Enhanced lighting system
    setup_enhanced_lighting()

    # Weather effects - removed (no rain, fog, or lightning)
    # draw_weather_effects()

    # ground and scenery (OPTIMIZED: Offset enabled once)
    draw_ground()
    glEnable(GL_POLYGON_OFFSET_FILL)
    glPolygonOffset(1.0, 1.0)
    draw_scenery()
    glDisable(GL_POLYGON_OFFSET_FILL)

    # car (third-person ensures car is visible)
    if not first_person_view:
        draw_car()

    # obstacles (filter visible only? But few, so unchanged)
    for o in obstacles:
        if abs(o.z - car_z) < view_dist:  # NEW: Skip far obstacles
            draw_obstacle(o)

    # bullets
    draw_bullets()

    # enemies
    draw_enemies()

    # Enhanced particle effects
    draw_particles()

    # HUD
    draw_speedometer_and_hud()

    if not game_active:
        # Game Over Screen - Freeze the game and show overlay
        draw_game_over()
    elif paused:
        draw_paused()

    glutSwapBuffers()

# update function (minor: Increased spawn delay already done globally)
frame_acc = 0
def update(value):
    global car_x, car_z, car_angle, camera_angle_horizontal, camera_angle_vertical, current_speed
    global first_person_view, game_active, next_obstacle_time, score, game_over_time
    global car_jump_height, car_jump_velocity, is_jumping, camera_shake, boost_meter, boosting, last_time
    global last_fire_time, day_mode, auto_day_night, lives
    # global weather_intensity, fog_density  # Removed - no weather effects

    global score_reported

    # Check if game is over first - freeze everything if so
    if not game_active:
        sound.engine_off()
        if not score_reported:
            report_score(score, game_over_time - game_start_time)
            score_reported = True
        # Check for restart key even when game is over
        if keys[b'r']:
            reset_game()
            keys[b'r'] = False
        elif time.time() > game_over_time + 5:
            reset_game()
        else:
            # Only update display, no game logic
            glutPostRedisplay()
            glutTimerFunc(16, update, 0)
            return

    # Paused: keep drawing the frozen frame, skip all game logic
    if paused:
        glutPostRedisplay()
        glutTimerFunc(16, update, 0)
        return

    now = time.time()
    dt = now - last_time if 'last_time' in globals() else 0.016
    # clamp dt to avoid giant jumps
    dt = min(dt, 0.05)
    # update particles
    update_particles(dt)

    # update bullets
    update_bullets(dt)

    # update enemies
    update_enemies(dt)

    # check bullet-enemy collisions
    check_bullet_enemy_collisions()

    if game_active:
        # spawn logic (varied by time) - uses global SPAWN_DELAY=2.0
        if time.time() > next_obstacle_time:
            # make more powerups at low speed / early game
            if random.random() < 0.15:
                spawn_powerup()
            else:
                spawn_obstacle()
            next_obstacle_time = time.time() + random.uniform(SPAWN_DELAY, SPAWN_DELAY+2.4)

        # Enemy spawning logic
        global enemy_spawn_timer
        enemy_spawn_timer += dt
        if enemy_spawn_timer >= enemy_spawn_interval:
            spawn_enemy()
            enemy_spawn_timer = 0.0

    # (rest of update unchanged - jump, view toggles, input, physics, collisions, etc.)
    # Jump input
    if keys[b'j'] and not is_jumping:
        is_jumping = True
        car_jump_velocity = jump_power
        keys[b'j'] = False

    if is_jumping:
        car_jump_height += car_jump_velocity * 0.1
        car_jump_velocity -= gravity * 0.18
        if car_jump_height <= 0:
            car_jump_height = 0
            car_jump_velocity = 0
            is_jumping = False

    # firing input - every F press / left click queues one shell; fire as soon as the gun is ready
    global pending_shots
    if pending_shots > 0 and (now - last_fire_time) >= fire_rate:
        fire_bullet()
        last_fire_time = now
        pending_shots -= 1

    # view toggles
    if keys[b'g']:
        first_person_view = True; keys[b'g'] = False
    if keys[b'h']:
        first_person_view = False; keys[b'h'] = False

    # headlight toggle - removed (no headlights on tank)
    # if keys[b'l']:
    #     headlights_on = not headlights_on
    #     keys[b'l'] = False

    # Weather controls - removed (no rain, fog, or lightning effects)
    # if keys[b't']:  # Toggle rain
    #     weather_intensity = 0.0 if weather_intensity > 0 else 0.7
    #     keys[b't'] = False
    # if keys[b'y']:  # Toggle fog
    #     fog_density = 0.0 if fog_density > 0 else 0.02
    #     keys[b'y'] = False

    # Mode switching (Day/Evening)
    if keys[b'c']:  # Toggle between automatic and manual day/night
        auto_day_night = not auto_day_night
        if not auto_day_night:
            # When switching to manual, toggle the current mode
            day_mode = 2 if day_mode == 1 else 1
        keys[b'c'] = False

    # Restart key handling moved to game over section above

    # camera control
    if keys['left']:
        camera_angle_horizontal += camera_rotation_speed * dt * 25.0
    if keys['right']:
        camera_angle_horizontal -= camera_rotation_speed * dt * 25.0
    if keys['up']:
        camera_angle_vertical += camera_vertical_speed * dt * 25.0
    if keys['down']:
        camera_angle_vertical -= camera_vertical_speed * dt * 25.0
    camera_angle_vertical = max(min_vertical_angle, min(max_vertical_angle, camera_angle_vertical))

    # steering: smoother lerp-based
    steer_amount = 0.0
    if keys[b'a']:
        steer_amount = steering_speed * dt
    elif keys[b'd']:
        steer_amount = -steering_speed * dt
    car_angle += steer_amount

    # Limit tank rotation to 130 degrees (-65 to +65 degrees)
    car_angle = max(-65.0, min(65.0, car_angle))

    # Enhanced acceleration / braking with particle effects
    if keys[b'w']:
        current_speed = min(current_speed + acceleration * dt * 30.0, max_speed)
        # Add exhaust particles when accelerating
        if current_speed > 1.0:
            add_particles(car_x - math.sin(math.radians(car_angle))*1.2, 0.2 + car_jump_height, car_z - math.cos(math.radians(car_angle))*1.2, count=4, color=(0.3,0.3,0.3))
    if keys[b's']:
        # S key now only applies brakes - no reverse movement
        if current_speed > 0:
            current_speed = max(current_speed - brake_deceleration * dt * 60.0, 0)
            # Add brake dust particles when braking
            if current_speed > 0.5:
                add_particles(car_x, 0.1 + car_jump_height, car_z, count=6, color=(0.5,0.4,0.3))

    # Enhanced braking (space) with brake dust particles
    if keys[b' ']:
        if current_speed > 0:
            current_speed = max(current_speed - brake_deceleration * dt * 60.0, 0)
            # Add brake dust particles
            if current_speed > 0.5:
                add_particles(car_x, 0.1 + car_jump_height, car_z, count=6, color=(0.5,0.4,0.3))
        elif current_speed < 0:
            current_speed = min(current_speed + brake_deceleration * dt * 60.0, 0)

    # natural drag
    if not (keys[b'w'] or keys[b' ']):
        if current_speed > 0:
            current_speed = max(current_speed - 0.3 * dt * 30.0, 0)
        # No reverse movement, so no need to handle negative speed

    # boost logic (press 1 for boost)
    global boosting
    if keys[b'1'] and boost_meter > 0.3:
        boosting = True
        keys[b'1'] = False
    if boosting:
        boost_meter = max(0.0, boost_meter - boost_consumption)
        current_speed = min(current_speed + 0.6, max_speed * 1.3)
        add_particles(car_x - math.sin(math.radians(car_angle))*1.2, 0.2 + car_jump_height, car_z - math.cos(math.radians(car_angle))*1.2, count=8, color=(0.2,0.6,1))
        if boost_meter <= 0: boosting = False
    else:
        boost_meter = min(boost_max, boost_meter + 0.01)

    # move car
    dx = current_speed * math.sin(math.radians(car_angle))
    dz = current_speed * math.cos(math.radians(car_angle))
    new_car_x = car_x + dx * 0.1
    new_car_z = car_z + dz * 0.1
    # clamp within road
    tank_width = 2.2  # Tank width (unchanged)
    car_x_clamp = road_width / 2 - tank_width / 2
    if new_car_x < car_x_clamp and new_car_x > -car_x_clamp:
        car_x = new_car_x
    else:
        car_x = max(min(new_car_x, car_x_clamp), -car_x_clamp)

    car_z = new_car_z

    # obstacle movement relative to world (we push obstacles toward car to simulate motion)
    if game_active:
        for obs in obstacles[:]:
            obs.z -= current_speed * 0.1  # obstacles scroll backwards

            if check_collision(obs) and not obs.hit:
                obs.hit = True
                obs.hit_time = time.time()
                # collision effects
                add_particles(obs.x, 0.6, obs.z, count=18, color=(1,0.4,0.1))
                camera_shake = 0.3
                # handle types
                if obs.type == 'good':
                    score += 12
                    current_speed = min(current_speed + 1.8, max_speed * 1.05)
                elif obs.type == 'bad':
                    score -= 5
                    current_speed = max(current_speed - 2.0, 0)
                    lives -= 1
                    sound.play_hit()
                    if lives <= 0:
                        game_active = False
                        game_over_time = time.time()
                        sound.play_game_over()
                elif obs.type == 'power':
                    sound.play_pickup()  # blue ball collected
                    if hasattr(obs, 'pu') and obs.pu == 'speed':
                        boost_meter = min(boost_max, boost_meter + 2.5)
                        score += 8
                    else:
                        # Blue powerups give +10 points and disappear immediately
                        score += 10
                        obstacles.remove(obs)  # Remove powerup immediately
                        continue  # Skip the rest of the loop for this obstacle
                # leave the obstacle for a short time to show hit effect
            # remove passed obstacles
            if obs.z < car_z - 25 and not obs.scored:
                if not obs.hit:
                    # rewarding avoidance
                    if obs.type == 'good':
                        score += 5
                    elif obs.type == 'bad':
                        score += 3
                obs.scored = True
                obstacles.remove(obs)

    # camera shake decay
    camera_shake *= 0.85

    # Barrel heat cooldown
    global barrel_heat, recoil_force
    barrel_heat = max(0.0, barrel_heat - barrel_cooldown_rate * dt)
    recoil_force *= 0.9  # Recoil decay

    # engine sound follows the tank's speed
    sound.set_engine(abs(current_speed) / max_speed, boosting)

    # update time reference
    last_time = now

    # Set next callback
    glutPostRedisplay()
    glutTimerFunc(16, update, 0)

# collision check considers jump (unchanged)
def check_collision(obstacle):
    tank_radius = 1.3  # Tank collision radius
    obs_radius = 0.9
    # if jumping high enough, pass over
    if is_jumping and car_jump_height > 0.8:
        return False
    dx = car_x - obstacle.x
    dz = car_z - obstacle.z
    return math.sqrt(dx*dx + dz*dz) < (tank_radius + obs_radius)

# -----------------------
# Input handlers (unchanged)
# -----------------------
def toggle_pause():
    global paused, pause_started, game_start_time, next_obstacle_time, last_fire_time, last_time
    if not game_active:
        return  # nothing to pause on the game over screen
    if not paused:
        paused = True
        pause_started = time.time()
        sound.pause()
        return
    # Resume: shift every wall-clock timer by the paused time so nothing "catches up" at once
    paused_for = time.time() - pause_started
    game_start_time += paused_for  # paused time doesn't count toward the score's play time
    next_obstacle_time += paused_for
    last_fire_time += paused_for
    last_time = time.time()
    paused = False
    sound.resume()

def queue_shot():
    global pending_shots
    if game_active and not paused:
        pending_shots = min(pending_shots + 1, MAX_PENDING_SHOTS)

def key_down(key, x, y):
    key = key.lower()  # Caps Lock / Shift send b'W' instead of b'w'
    if key in (b'p', b'\x1b'):  # P or Esc
        keys[b'p'] = True
        toggle_pause()
        return
    if paused and key == b'r':
        reset_game()  # restart straight from the pause screen
        return
    if key == b'f':
        queue_shot()
    if key == b'm':
        sound.toggle_mute()
    if key in keys:
        keys[key] = True

def key_up(key, x, y):
    key = key.lower()
    if key == b'\x1b':
        key = b'p'
    if key in keys:
        keys[key] = False

def special_down(key, x, y):
    if key == GLUT_KEY_UP: keys['up'] = True
    elif key == GLUT_KEY_DOWN: keys['down'] = True
    elif key == GLUT_KEY_LEFT: keys['left'] = True
    elif key == GLUT_KEY_RIGHT: keys['right'] = True

def special_up(key, x, y):
    if key == GLUT_KEY_UP: keys['up'] = False
    elif key == GLUT_KEY_DOWN: keys['down'] = False
    elif key == GLUT_KEY_LEFT: keys['left'] = False
    elif key == GLUT_KEY_RIGHT: keys['right'] = False

def reshape(w, h):
    """Keep the 3D view correct when the window is resized or maximized."""
    h = max(h, 1)
    glViewport(0, 0, w, h)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(60, w / h, 1.0, 1000.0)
    glMatrixMode(GL_MODELVIEW)

def mouse_click(button, state, x, y):
    """Handle mouse clicks for firing bullets"""
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        queue_shot()  # same as pressing F

# -----------------------
# Main (unchanged)
# -----------------------
def main():
    print("✨ Tank Raider (Optimized for Performance)")
    print("Controls: W/A/S/D accelerate/steer, Space = brake, J = jump, Left Click = fire shell, 1 = boost, G/H = view, C = auto/manual day/night, R = reset")
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    # Fit the window on screen (laptops with 125% scaling only have ~816px of height),
    # otherwise the bottom control buttons end up below the taskbar
    screen_w, screen_h = glutGet(GLUT_SCREEN_WIDTH), glutGet(GLUT_SCREEN_HEIGHT)
    win_h = min(768, int(screen_h * 0.80))
    win_w = min(int(win_h * 4 / 3), screen_w - 40)
    glutInitWindowSize(win_w, win_h)
    glutInitWindowPosition(max(0, (screen_w - win_w) // 2), max(0, (screen_h - win_h) // 2 - 40))
    glutCreateWindow(b"Tank Raider")
    init()
    sound.init()
    reset_game()
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutIgnoreKeyRepeat(1)  # one shell per F press, even if the key is held
    glutKeyboardFunc(key_down)
    glutKeyboardUpFunc(key_up)
    glutSpecialFunc(special_down)
    glutSpecialUpFunc(special_up)
    glutMouseFunc(mouse_click)  
    glutTimerFunc(16, update, 0)
    glutMainLoop()

if __name__ == "__main__":
    main()
