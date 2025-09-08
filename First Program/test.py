# enhanced_car_game_beauty.py
# Requires: PyOpenGL, GLUT (usually freeglut)
# Run: python enhanced_car_game_beauty.py

import math
import random
import sys
import time

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

# -----------------------
# Game state (kept & extended)
# -----------------------
bark_texture_id = None
game_start_time = time.time()
day_mode = 1  # 1=day, 2=evening, 3=night
headlights_on = False
car_x, car_z = 0.0, 0.0
car_angle = 0.0
current_speed = 0.0
max_speed = 10.0

acceleration = 0.35
deceleration = 0.5
brake_deceleration = 1.0
car_width = 1.5 * 0.81
car_length = 3.0 * 0.81
car_height = 1.2 * 0.81
steering_speed = 60.0  # degrees per second (for smoother steering)
wheel_rotation_angle = 0.0
first_person_view = False
game_active = True
score = 0
time_of_day = 6 * 60  # minutes; start at 6:00
obstacles = []
powerups = []
next_obstacle_time = 0
game_over_time = 0
lives = 3

# Jump
car_jump_height = 0.0
car_jump_velocity = 0.0
is_jumping = False
jump_power = 3.75
gravity = 1.5



# Camera
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
building_spacing = 20
# tree_spacing = 30
view_dist = 200  # NEW: Visible range for optimization (ahead/behind car)
WINDOWS_PER_BUILDING = 4  # REDUCED: From 6 to 4 for fewer windows

# Procedural heights
building_heights = {}
tree_heights = {}

# Input state
keys = {
    b'w': False, b's': False, b'a': False, b'd': False, b' ': False, b'r': False, b'l': False,
    b'1': False, b'2': False, b'3': False, b'g': False, b'h': False, b'j': False, b'f': False,
    'left': False, 'right': False, 'up': False, 'down': False, b'q': False, b'e': False
}

# Particles
particles = []

# Bullets
bullets = []
bullet_speed = 300.0  # Higher bullet speed for better gameplay
max_bullets = 50

# Enemies
enemies = []
enemy_spawn_timer = 0.0
enemy_spawn_interval = 3.0  # Spawn enemy every 3 seconds
max_enemies = 10

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
    def __init__(self, x, y, z, vx, vy, vz):
        self.x = x
        self.y = y
        self.z = z
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.life = 3.0  # Bullet lifetime in seconds
        self.age = 0.0
        self.radius = 0.1
        self.color = (1.0, 1.0, 0.0)  # Yellow bullet

class Enemy:
    def __init__(self, x, z):
        self.x = x
        self.y = 0.0
        self.z = z
        self.speed = 8.0 + random.random() * 4.0  # Faster speed between 8-12
        self.radius = 0.8
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
    global enemies, enemy_spawn_timer
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
    lives = 3
    car_jump_height = 0.0
    car_jump_velocity = 0.0
    is_jumping = False
    boost_meter = boost_max / 2

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
    global bullets
    if len(bullets) >= max_bullets:
        return  # Limit number of bullets

    # Calculate bullet starting position (from gun barrel tip)
    # Gun is positioned at car center, extends 1.7 units forward
    gun_x = car_x + 1.7 * math.sin(math.radians(car_angle))
    gun_y = car_height/2 + car_jump_height + 0.3 + 0.2  # Higher gun position for better range
    gun_z = car_z + 1.7 * math.cos(math.radians(car_angle))

    # Calculate bullet direction (forward from car) - match car movement exactly
    bullet_vx = bullet_speed * math.sin(math.radians(car_angle))
    bullet_vy = 0.0  # No vertical velocity initially
    bullet_vz = bullet_speed * math.cos(math.radians(car_angle))

    # Create new bullet
    bullet = Bullet(gun_x, gun_y, gun_z, bullet_vx, bullet_vy, bullet_vz)
    bullets.append(bullet)

def update_bullets(dt):
    global bullets
    for bullet in bullets[:]:
        bullet.age += dt
        if bullet.age >= bullet.life:
            bullets.remove(bullet)
            continue

        # Update bullet position
        bullet.x += bullet.vx * dt
        bullet.y += bullet.vy * dt
        bullet.z += bullet.vz * dt

        # Apply gravity to bullets
        bullet.vy -= 9.8 * dt * 0.5

        # Remove bullets that are too far away
        if (abs(bullet.x) > 200 or bullet.y < -10 or
            abs(bullet.z - car_z) > 300):
            bullets.remove(bullet)

def draw_bullets():
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    for bullet in bullets:
        glPushMatrix()
        glTranslatef(bullet.x, bullet.y, bullet.z)
        glColor3f(*bullet.color)
        glutSolidSphere(bullet.radius, 8, 8)
        glPopMatrix()

    glDisable(GL_BLEND)

def spawn_enemy():
    global enemies, enemy_spawn_timer
    if len(enemies) >= max_enemies:
        return

    # Spawn enemy ahead of the car in the road
    spawn_distance = 50.0 + random.random() * 30.0  # 50-80 units ahead
    spawn_x = (random.random() - 0.5) * 8.0  # Random position across road width
    spawn_z = car_z + spawn_distance

    enemy = Enemy(spawn_x, spawn_z)
    enemies.append(enemy)

def update_enemies(dt):
    global enemies, score
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
        if distance_to_car < (enemy.radius + 1.0):  # Car radius ~1.0
            # Check if car is jumping high enough to clear the enemy
            car_height_above_ground = car_jump_height
            enemy_height = 1.6  # Approximate height of humanoid enemy (head to feet)

            if is_jumping and car_height_above_ground > enemy_height * 0.7:  # Need to clear 70% of enemy height
                # Successfully jumped over enemy - no penalty, enemy continues
                continue
            else:
                # Car collision with enemy (not jumping or not high enough)
                score -= 5
                enemies.remove(enemy)
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

        # BODY (red cube)
        glColor3f(enemy.color[0] * intensity, enemy.color[1] * intensity, enemy.color[2] * intensity)
        glPushMatrix()
        glTranslatef(0, 0.6, 0)
        glScalef(0.6, 0.8, 0.4)
        glutSolidCube(1)
        glPopMatrix()

        # ARMS (red cylinders)
        arm_swing = 0.3 * math.sin(enemy.walk_cycle)
        glPushMatrix()
        glTranslatef(-0.5, 0.7, 0)
        glRotatef(arm_swing * 30, 1, 0, 0)  # Arm swinging
        glRotatef(90, 0, 1, 0)
        glutSolidCylinder(0.1, 0.6, 6, 6)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(0.5, 0.7, 0)
        glRotatef(-arm_swing * 30, 1, 0, 0)  # Opposite arm swinging
        glRotatef(90, 0, 1, 0)
        glutSolidCylinder(0.1, 0.6, 6, 6)
        glPopMatrix()

        # HANDS (red spheres)
        glPushMatrix()
        glTranslatef(-0.5 - 0.6 * math.cos(arm_swing * 0.5), 0.7, 0.6 * math.sin(arm_swing * 0.5))
        glutSolidSphere(0.12, 6, 6)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0.5 + 0.6 * math.cos(arm_swing * 0.5), 0.7, 0.6 * math.sin(arm_swing * 0.5))
        glutSolidSphere(0.12, 6, 6)
        glPopMatrix()

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

def check_bullet_enemy_collisions():
    global bullets, enemies, score
    for bullet in bullets[:]:
        for enemy in enemies[:]:
            # Calculate distance between bullet and enemy
            distance = math.sqrt((bullet.x - enemy.x)**2 + (bullet.y - enemy.y)**2 + (bullet.z - enemy.z)**2)

            if distance < (bullet.radius + enemy.radius + 0.3):  # More forgiving collision detection
                # Collision detected
                bullets.remove(bullet)
                enemies.remove(enemy)
                score += 10  # +10 points for killing enemy
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
    elif day_mode == 2:
        top = (0.12, 0.1, 0.25)
        bottom = (0.9, 0.5, 0.3)
    else:
        top = (0.01, 0.02, 0.07)
        bottom = (0.02, 0.04, 0.08)
    glColor3f(*top); glVertex3f(-200, 200, -200)
    glColor3f(*top); glVertex3f(200, 200, -200)
    glColor3f(*bottom); glVertex3f(200, -10, -200)
    glColor3f(*bottom); glVertex3f(-200, -10, -200)
    glEnd()
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()

def draw_ground():
    # big ground (unchanged)
    if day_mode == 1:
        ground_col = (0.2, 0.6, 0.25)
    elif day_mode == 2:
        ground_col = (0.12, 0.25, 0.12)
    else:
        ground_col = (0.03, 0.06, 0.02)

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
    elif day_mode == 2:
        road_col = (0.12, 0.12, 0.12)
    else:
        road_col = (0.06, 0.06, 0.08)
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
    highlight = 0.06 if day_mode==1 else 0.12
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
    mark_col = (1,1,1) if day_mode==1 else (0.7,0.7,0.8)

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
    global building_states
    key = (x, z)  # unique ID for each building

    if key not in building_states:
        # ----------------------------
        # INITIALIZE BUILDING STATE (unchanged, but reduced windows)
        # ----------------------------
        state = {}

        # Pick a vibrant facade color with variation
        facade_colors = [
            (0.9, 0.6, 0.6),  # soft coral
            (0.6, 0.9, 0.7),  # mint green
            (0.7, 0.7, 0.95), # soft sky blue
            (0.95, 0.85, 0.6), # warm beige
            (0.85, 0.7, 0.9),  # lavender
            (0.65, 0.9, 0.95)  # aqua
        ]
        chosen = random.choice(facade_colors)
        state["color"] = (
            chosen[0] * random.uniform(0.9, 1.1),
            chosen[1] * random.uniform(0.9, 1.1),
            chosen[2] * random.uniform(0.9, 1.1)
        )

        # Precompute window states with fewer windows
        windows = []
        num_rows = WINDOWS_PER_BUILDING // 2 * 2  # Even number
        for r in range(-num_rows//2, num_rows//2):
            row_states = []
            for c in range(-2, 3):  # REDUCED: 5 cols instead of 7
                row_states.append(random.random() > 0.3)  # lit or dark
            windows.append(row_states)
        state["windows"] = windows

        building_states[key] = state

    # Retrieve persistent state
    state = building_states[key]
    col = state["color"]
    windows = state["windows"]

    glPushMatrix()
    glTranslatef(x, scale_y / 2 + 0.1, z + 0.1)  # Slight elevation and z-offset for visibility

    # Save/restore all attributes to minimize state changes (NEW)
    glPushAttrib(GL_ALL_ATTRIB_BITS)

    # Enable and configure depth testing
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LESS)
    glEnable(GL_CULL_FACE)  # Prevent backface rendering issues

    # ----------------------------
    # APPLY TIME OF DAY COLOR ADJUSTMENTS (unchanged)
    # ----------------------------
    if day_mode == 2:  # dusk
        col = tuple(c * 0.75 for c in col)
    elif day_mode == 3:  # night
        col = tuple(c * 0.45 for c in col)

    # ----------------------------
    # MAIN BUILDING BODY WITH TEXTURE EFFECT (unchanged)
    # ----------------------------
    glColor3f(col[0] * 0.9, col[1] * 0.9, col[2] * 0.9)  # Slight shadow for depth
    glScalef(scale_x, scale_y, scale_z)
    glutSolidCube(1)
    glScalef(1/scale_x, 1/scale_y, 1/scale_z)

    # Add subtle facade lines (unchanged)
    glColor3f(0.8, 0.8, 0.8)
    glBegin(GL_LINES)
    for i in range(-5, 6):
        glVertex3f(-0.5, i * 0.2, 0.51)
        glVertex3f(0.5, i * 0.2, 0.51)
    glEnd()

    # Base texture (unchanged)
    glColor3f(0.5, 0.5, 0.5)
    glBegin(GL_QUADS)
    glVertex3f(-0.5, -0.5, 0.51)
    glVertex3f( 0.5, -0.5, 0.51)
    glVertex3f( 0.5, -0.48, 0.51)
    glVertex3f(-0.5, -0.48, 0.51)
    glEnd()

    # ----------------------------
    # WINDOWS WITH FRAMES (Simplified: Front and Right only, fewer windows)
    # ----------------------------
    glBegin(GL_QUADS)
    num_rows = len(windows)
    for ri, r in enumerate(range(-num_rows//2, num_rows//2)):
        # Front face (z+) - REDUCED cols
        for ci, c in enumerate(range(-2, 3)):
            xx = -0.48 + 0.16 * (c + 2)
            yy = 0.18 * r

            # Window frame (gray)
            glColor3f(0.4, 0.4, 0.4)
            glVertex3f(xx + 0.06, yy + 0.06, 0.51)
            glVertex3f(xx + 0.06, yy + 0.16, 0.51)
            glVertex3f(xx - 0.06, yy + 0.16, 0.51)
            glVertex3f(xx - 0.06, yy + 0.06, 0.51)

            # Window sill (simplified, one quad)
            glColor3f(0.6, 0.6, 0.6)
            glVertex3f(xx + 0.07, yy + 0.05, 0.52)
            glVertex3f(xx - 0.07, yy + 0.05, 0.52)
            glVertex3f(xx - 0.07, yy + 0.04, 0.52)
            glVertex3f(xx + 0.07, yy + 0.04, 0.52)

            # Window glass color by time of day
            if day_mode == 3:  # night
                if windows[ri][ci]:
                    window_col = (1.0, 0.95, 0.7)  # glowing yellow
                else:
                    window_col = (0.1, 0.1, 0.1)  # darker
            elif day_mode == 2:  # dusk
                window_col = (0.75, 0.55, 0.35)  # warm tone
            else:  # day
                window_col = (0.6, 0.7, 0.8)  # reflective glass

            glColor3f(*window_col)
            glVertex3f(xx + 0.05, yy + 0.05, 0.52)
            glVertex3f(xx + 0.05, yy + 0.15, 0.52)
            glVertex3f(xx - 0.05, yy + 0.15, 0.52)
            glVertex3f(xx - 0.05, yy + 0.05, 0.52)

        # Right side face (x+) - REDUCED cols/windows
        for ci, c in enumerate(range(-1, 2)):  # Even fewer
            xx = 0.48
            yy = 0.18 * r
            zz = -0.45 + 0.18 * (c + 1)

            # Window frame (gray)
            glColor3f(0.4, 0.4, 0.4)
            glVertex3f(xx + 0.01, yy + 0.06, zz + 0.06)
            glVertex3f(xx + 0.01, yy + 0.16, zz + 0.06)
            glVertex3f(xx + 0.01, yy + 0.16, zz - 0.06)
            glVertex3f(xx + 0.01, yy + 0.06, zz - 0.06)

            # Window sill
            glColor3f(0.6, 0.6, 0.6)
            glVertex3f(xx + 0.02, yy + 0.05, zz + 0.07)
            glVertex3f(xx + 0.02, yy + 0.05, zz - 0.07)
            glVertex3f(xx + 0.01, yy + 0.04, zz - 0.07)
            glVertex3f(xx + 0.01, yy + 0.04, zz + 0.07)

            # Window glass
            if day_mode == 3:
                if ri < len(windows) and ci < len(windows[ri]):
                    if windows[ri][ci]:
                        window_col = (1.0, 0.95, 0.7)
                    else:
                        window_col = (0.1, 0.1, 0.1)
                else:
                    window_col = (0.1, 0.1, 0.1)
            elif day_mode == 2:
                window_col = (0.75, 0.55, 0.35)
            else:
                window_col = (0.6, 0.7, 0.8)

            glColor3f(*window_col)
            glVertex3f(xx, yy + 0.05, zz + 0.05)
            glVertex3f(xx, yy + 0.15, zz + 0.05)
            glVertex3f(xx, yy + 0.15, zz - 0.05)
            glVertex3f(xx, yy + 0.05, zz - 0.05)

    glEnd()  # FIXED: End the big GL_QUADS batch

    # ----------------------------
    # DOOR WITH FRAME (Front and Right Side) (unchanged)
    # ----------------------------
    glBegin(GL_QUADS)
    # Front door frame
    glColor3f(col[0] * 0.3, col[1] * 0.2, col[2] * 0.2)
    glVertex3f(-0.12, -0.52, 0.51)
    glVertex3f( 0.12, -0.52, 0.51)
    glVertex3f( 0.12, -0.2, 0.51)
    glVertex3f(-0.12, -0.2, 0.51)

    # Front door
    glColor3f(col[0] * 0.5, col[1] * 0.35, col[2] * 0.35)
    glVertex3f(-0.1, -0.5, 0.52)
    glVertex3f( 0.1, -0.5, 0.52)
    glVertex3f( 0.1, -0.22, 0.52)
    glVertex3f(-0.1, -0.22, 0.52)

    # Right side door frame
    glColor3f(col[0] * 0.3, col[1] * 0.2, col[2] * 0.2)
    glVertex3f(0.51, -0.52, -0.12)
    glVertex3f(0.51, -0.52,  0.12)
    glVertex3f(0.51, -0.2,   0.12)
    glVertex3f(0.51, -0.2,  -0.12)

    # Right side door
    glColor3f(col[0] * 0.5, col[1] * 0.35, col[2] * 0.35)
    glVertex3f(0.52, -0.5, -0.1)
    glVertex3f(0.52, -0.5,  0.1)
    glVertex3f(0.52, -0.22, 0.1)
    glVertex3f(0.52, -0.22, -0.1)
    glEnd()

    # Add roof detail (unchanged)
    glColor3f(0.6, 0.6, 0.6)
    glBegin(GL_QUADS)
    glVertex3f(-0.5, scale_y / 2, 0.51)
    glVertex3f( 0.5, scale_y / 2, 0.51)
    glVertex3f( 0.5, scale_y / 2 + 0.05, 0.51)
    glVertex3f(-0.5, scale_y / 2 + 0.05, 0.51)
    glEnd()

    glPopAttrib()  # Restore states
    glDisable(GL_CULL_FACE)  # Ensure disabled
    glPopMatrix()

def draw_building(x, z, scale_x, scale_y, scale_z, color):
    glPushMatrix()
    glTranslatef(x, scale_y / 2, z)
    glScalef(scale_x, scale_y, scale_z)

    # main building cube
    glColor3f(*color)
    glutSolidCube(1.0)
    glPopMatrix()

    # -------------------------
    # Helper to draw a door
    # -------------------------
    def draw_door(dx, dz, facing):
        door_w = scale_x * 0.4
        door_h = min(2.0, scale_y * 0.3)
        glColor3f(0.4, 0.2, 0.1)  # brown
        glBegin(GL_QUADS)
        if facing == "front":
            glVertex3f(dx - door_w/2, 0, dz)
            glVertex3f(dx - door_w/2, door_h, dz)
            glVertex3f(dx + door_w/2, door_h, dz)
            glVertex3f(dx + door_w/2, 0, dz)
        elif facing == "back":
            glVertex3f(dx - door_w/2, 0, dz)
            glVertex3f(dx - door_w/2, door_h, dz)
            glVertex3f(dx + door_w/2, door_h, dz)
            glVertex3f(dx + door_w/2, 0, dz)
        elif facing == "left":
            glVertex3f(dx, 0, dz - door_w/2)
            glVertex3f(dx, door_h, dz - door_w/2)
            glVertex3f(dx, door_h, dz + door_w/2)
            glVertex3f(dx, 0, dz + door_w/2)
        elif facing == "right":
            glVertex3f(dx, 0, dz - door_w/2)
            glVertex3f(dx, door_h, dz - door_w/2)
            glVertex3f(dx, door_h, dz + door_w/2)
            glVertex3f(dx, 0, dz + door_w/2)
        glEnd()

    # -------------------------
    # Helper to draw windows
    # -------------------------
    def draw_windows(face):
        rows = int(scale_y // 2)
        cols = 3
        win_w = scale_x / (cols + 1)
        win_h = scale_y / (rows + 3)

        for r in range(1, rows):
            for c in range(cols):
                # color depending on day/night
                if day_mode == 3:  # night
                    if random.random() > 0.5:
                        glass = (1.0, 1.0, 0.6)
                    else:
                        glass = (0.1, 0.1, 0.1)
                else:
                    glass = (0.6, 0.7, 0.9)

                # front & back faces (Z direction)
                if face == "front":
                    wx = x - scale_x/2 + (c+1)*win_w
                    wy = r*win_h + 1.0
                    wz = z + scale_z/2 + 0.01
                elif face == "back":
                    wx = x - scale_x/2 + (c+1)*win_w
                    wy = r*win_h + 1.0
                    wz = z - scale_z/2 - 0.01
                # left & right faces (X direction)
                elif face == "left":
                    wx = x - scale_x/2 - 0.01
                    wy = r*win_h + 1.0
                    wz = z - scale_z/2 + (c+1)*win_w
                elif face == "right":
                    wx = x + scale_x/2 + 0.01
                    wy = r*win_h + 1.0
                    wz = z - scale_z/2 + (c+1)*win_w

                # draw quad window
                glColor3f(*glass)
                glBegin(GL_QUADS)
                if face in ["front", "back"]:
                    glVertex3f(wx - win_w/3, wy - win_h/3, wz)
                    glVertex3f(wx - win_w/3, wy + win_h/3, wz)
                    glVertex3f(wx + win_w/3, wy + win_h/3, wz)
                    glVertex3f(wx + win_w/3, wy - win_h/3, wz)
                else:  # left/right face
                    glVertex3f(wx, wy - win_h/3, wz - win_w/3)
                    glVertex3f(wx, wy + win_h/3, wz - win_w/3)
                    glVertex3f(wx, wy + win_h/3, wz + win_w/3)
                    glVertex3f(wx, wy - win_h/3, wz + win_w/3)
                glEnd()

    # -------------------------
    # Place doors
    # -------------------------
    draw_door(x, z + scale_z/2 + 0.01, "front")
    draw_door(x, z - scale_z/2 - 0.01, "back")
    draw_door(x - scale_x/2 - 0.01, z, "left")
    draw_door(x + scale_x/2 + 0.01, z, "right")

    # -------------------------
    # Place windows
    # -------------------------
    draw_windows("front")
    draw_windows("back")
    draw_windows("left")
    draw_windows("right")

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




def draw_car():
    glPushMatrix()
    glTranslatef(car_x, car_height/2 + car_jump_height, car_z)
    glRotatef(car_angle, 0, 1, 0)

    # Draw existing car components
    draw_enhanced_car_body()
    draw_windows()
    draw_wheels()
    draw_lights()

    # Draw shooter gun on the roof
    glPushMatrix()
    # Position gun on the roof (at car_height above car center)
    glTranslatef(0, car_height/2 + 0.1, 0)  # Slightly above roof level for visibility

    # Save attributes to avoid state leaks
    glPushAttrib(GL_ALL_ATTRIB_BITS)

    # Gun base (larger, more visible)
    glColor3f(0.15, 0.15, 0.15)  # Dark gray base
    glPushMatrix()
    glScalef(0.6, 0.25, 0.6)  # Larger base for better visibility
    glutSolidCube(1)
    glPopMatrix()

    # Gun barrel (thicker cylinder for better visibility)
    glColor3f(0.25, 0.25, 0.25)  # Medium gray barrel
    glPushMatrix()
    glTranslatef(0, 0.1, 0.6)  # Extend barrel forward from center
    glRotatef(90, 1, 0, 0)  # Rotate to point forward (along car's z-axis)
    glutSolidCylinder(0.15, 1.1, 12, 8)  # Thicker, shorter cylinder (radius 0.15, length 1.1)
    glPopMatrix()

    # Gun tip removed - no black dot in front of car

    # Add gun mount details
    glColor3f(0.2, 0.2, 0.2)  # Dark gray mount
    glPushMatrix()
    glTranslatef(0, 0.05, 0)  # Slightly below base
    glScalef(0.4, 0.1, 0.4)  # Smaller mount
    glutSolidCube(1)
    glPopMatrix()

    glPopAttrib()
    glPopMatrix()

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

def draw_lights():
    light_size = 0.15  # Larger headlights
    light_height = -0.15  # Slightly higher position

    # Enhanced headlight housings (black)
    glColor3f(0.05, 0.05, 0.05)  # Very dark black housing
    glPushMatrix()
    glTranslatef(-car_width/2 * 0.85, light_height, car_length/2 * 0.9)
    glScalef(0.3, 0.2, 0.2)
    glutSolidCube(1)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(car_width/2 * 0.85, light_height, car_length/2 * 0.9)
    glScalef(0.3, 0.2, 0.2)
    glutSolidCube(1)
    glPopMatrix()

    # Headlight beams (when on)
    if headlights_on:
        glPushMatrix()
        glTranslatef(0, light_height, car_length/2 * 0.92)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glColor4f(1.0, 0.95, 0.7, 0.3)  # Brighter yellow beam
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, 0, 0)
        glVertex3f(-2.0, 0, 10.0)  # Wider and longer beam
        glVertex3f(2.0, 0, 10.0)
        glEnd()
        glDisable(GL_BLEND)
        glPopMatrix()

    # Headlight bulbs (brighter when on)
    if headlights_on:
        glColor3f(1.0, 0.95, 0.7)  # Bright yellow when on
    else:
        glColor3f(0.4, 0.4, 0.3)  # Dim gray when off

    glPushMatrix()
    glTranslatef(-car_width/2 * 0.85, light_height, car_length/2 * 0.9)
    glutSolidSphere(light_size, 12, 12)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(car_width/2 * 0.85, light_height, car_length/2 * 0.9)
    glutSolidSphere(light_size, 12, 12)
    glPopMatrix()

    # Add headlight rings for detail
    glColor3f(0.2, 0.2, 0.2)  # Dark gray rings
    glPushMatrix()
    glTranslatef(-car_width/2 * 0.85, light_height, car_length/2 * 0.9)
    glutSolidTorus(0.02, light_size + 0.05, 8, 16)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(car_width/2 * 0.85, light_height, car_length/2 * 0.9)
    glutSolidTorus(0.02, light_size + 0.05, 8, 16)
    glPopMatrix()
    # Red backlights - always on
    glColor3f(1.0, 0.1, 0.1)  # Bright red backlights

    # Main backlights (spheres)
    glPushMatrix()
    glTranslatef(-car_width/2 * 0.8, light_height, -car_length/2 * 0.9)
    glutSolidSphere(0.15, 8, 8)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(car_width/2 * 0.8, light_height, -car_length/2 * 0.9)
    glutSolidSphere(0.15, 8, 8)
    glPopMatrix()

    # Two small rectangle-shaped backlights
    glColor3f(1.0, 0.0, 0.0)  # Bright red rectangles
    glPushMatrix()
    glTranslatef(-car_width/2 * 0.3, light_height + 0.05, -car_length/2 * 0.9)
    glScalef(0.15, 0.08, 0.02)  # Small rectangle shape
    glutSolidCube(1)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(car_width/2 * 0.3, light_height + 0.05, -car_length/2 * 0.9)
    glScalef(0.15, 0.08, 0.02)  # Small rectangle shape
    glutSolidCube(1)
    glPopMatrix()

    # Brake lights (brighter when braking)
    if current_speed < 0 or keys[b' ']:
        glColor3f(1.0, 0.0, 0.0)  # Very bright red when braking
        # Add light glow effect
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glColor4f(1.0, 0.0, 0.0, 0.3)
        glPushMatrix()
        glTranslatef(0, light_height, -car_length/2 * 0.9)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, 0, 0)
        glVertex3f(-2.0, 0, -3.0)
        glVertex3f(2.0, 0, -3.0)
        glEnd()
        glDisable(GL_BLEND)

def draw_obstacle(o):
    glPushMatrix()
    glTranslatef(o.x, 0.4 + 0.2, o.z)  # All obstacles are powerups now
    glColor3f(*o.color)
    # All obstacles are now blue powerups
    # spin sphere to signal power-up
    glRotatef((time.time()*60)%360, 0, 1, 0)
    glutSolidSphere(o.scale, 12, 12)  # Round sphere shape
    glPopMatrix()

def draw_minimap():
    # (unchanged)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, 100, 0, 100, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    # circle background
    cx, cy, r = 84, 84, 10
    glColor3f(0.06, 0.06, 0.06)
    glBegin(GL_TRIANGLE_FAN)
    glVertex2f(cx, cy)
    for i in range(361):
        a = i * math.pi * 2 / 360.0
        glVertex2f(cx + math.cos(a) * r, cy + math.sin(a) * r)
    glEnd()
    # indicator
    mapped_z = cy + ((car_z - scene_start) / max(1, (scene_end - scene_start))) * (2*r - 4) - (r - 2)
    glColor3f(0.2, 0.9, 0.2)
    glPointSize(6)
    glBegin(GL_POINTS)
    glVertex2f(cx, mapped_z)
    glEnd()
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_speedometer_and_hud():
    speed_kmh = abs(current_speed) * 3.6
    glMatrixMode(GL_PROJECTION)
    glPushMatrix(); glLoadIdentity(); gluOrtho2D(0, 800, 0, 600)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix(); glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    # score box
    glColor3f(0.05, 0.05, 0.06)
    glBegin(GL_QUADS); glVertex2f(10, 550); glVertex2f(210, 550); glVertex2f(210, 590); glVertex2f(10, 590); glEnd()
    glColor3f(1,1,1)
    draw_text(15, 570, f"Score: {score}")
    draw_text(15, 555, f"Lives: {lives}")
    draw_text(15, 540, f"Time: {int(time_of_day//60):02d}:{int(time_of_day%60):02d}")
    # speed meter
    draw_text(650, 565, f"Speed: {speed_kmh:.0f} km/h")
    # boost meter
    draw_text(650, 545, f"Boost: {boost_meter:.1f}/{boost_max}")
    # Jump status
    jump_text = "JUMPING!" if is_jumping else "Press J to Jump"
    draw_text(650, 525, jump_text)
    # Firing status
    draw_text(650, 485, f"Press F to Fire ({len(bullets)}/{max_bullets})")
    # mode text
    mode_text = ["Day Mode", "Evening Mode", "Night Mode"][day_mode-1]
    draw_text(650, 465, mode_text)
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_12):
    glColor3f(1.0, 1.0, 1.0)
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

# -----------------------
# Display and update loop (minor: Enable offset once)
# -----------------------
last_time = time.time()
def display():
    global time_of_day, day_mode, headlights_on
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    # time progression (unchanged)
    if game_active:
        time_of_day += 0.5
        if time_of_day >= 24*60: time_of_day -= 24*60

    # determine mode and background color (unchanged)
    if 5*60 <= time_of_day < 6*60:
        day_mode = 1
        r = 0.7 + 0.3*(time_of_day-300)/60
        g = 0.5 + 0.3*(time_of_day-300)/60
        b = 0.3 + 0.5*(time_of_day-300)/60
    elif 6*60 <= time_of_day < 18*60:
        r,g,b = (0.5, 0.8, 1.0); day_mode = 1
    elif 18*60 <= time_of_day < 19*60:
        t = (time_of_day-1080)/60.0
        r = 0.5 - 0.3*t; g = 0.8 - 0.4*t; b = 1.0 - 0.7*t
        day_mode = 2
    elif 19*60 <= time_of_day < 21*60:
        r,g,b = (0.02, 0.02, 0.08); day_mode = 3
    else:
        r,g,b = (0.01, 0.01, 0.04); day_mode = 3

    headlights_on = (time_of_day >= 18*60) or (time_of_day < 5*60)

    # sky
    glClearColor(r, g, b, 1.0)
    draw_sky()

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

    # Draw sun in fixed world coordinates (independent of camera/car)
    # draw_sun()

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

    # particles (commented out as before)
    # draw_particles()

    # HUD
    draw_minimap()
    draw_speedometer_and_hud()

    if not game_active:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,800,0,600)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix(); glLoadIdentity()
        draw_text(320, 300, f"GAME OVER! Final Score: {score}", GLUT_BITMAP_HELVETICA_18)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    glutSwapBuffers()

# update function (minor: Increased spawn delay already done globally)
frame_acc = 0
def update(value):
    global car_x, car_z, car_angle, camera_angle_horizontal, camera_angle_vertical, current_speed
    global headlights_on, first_person_view, game_active, next_obstacle_time, score, game_over_time
    global car_jump_height, car_jump_velocity, is_jumping, camera_shake, boost_meter, boosting, last_time

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

    # firing input
    if keys[b'f']:
        fire_bullet()
        keys[b'f'] = False

    # view toggles
    if keys[b'g']:
        first_person_view = True; keys[b'g'] = False
    if keys[b'h']:
        first_person_view = False; keys[b'h'] = False

    # headlight toggle (only meaningful at night)
    if keys[b'l']:
        headlights_on = not headlights_on
        keys[b'l'] = False

    if keys[b'r']:
        reset_game(); keys[b'r'] = False

    # camera control
    if keys['left'] or keys[b'q']:
        camera_angle_horizontal += camera_rotation_speed * dt * 25.0
    if keys['right'] or keys[b'e']:
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

    # acceleration / braking
    if keys[b'w']:
        current_speed = min(current_speed + acceleration * dt * 40.0, max_speed)
    if keys[b's']:
        current_speed = max(current_speed - deceleration * dt * 40.0, -max_speed*0.4)

    # braking (space)
    if keys[b' ']:
        if current_speed > 0:
            current_speed = max(current_speed - brake_deceleration * dt * 80.0, 0)
        elif current_speed < 0:
            current_speed = min(current_speed + brake_deceleration * dt * 80.0, 0)

    # natural drag
    if not (keys[b'w'] or keys[b's'] or keys[b' ']):
        if current_speed > 0:
            current_speed = max(current_speed - 0.3 * dt * 40.0, 0)
        elif current_speed < 0:
            current_speed = min(current_speed + 0.3 * dt * 40.0, 0)

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
    car_x_clamp = road_width / 2 - car_width / 2
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
                elif obs.type == 'power':
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
    # update time reference
    last_time = now

    # particles are updated earlier; set next callback
    if not game_active:
        if time.time() > game_over_time + 5:
            reset_game()
        else:
            glutPostRedisplay()
            glutTimerFunc(16, update, 0)
            return

    glutPostRedisplay()
    glutTimerFunc(16, update, 0)

# collision check considers jump (unchanged)
def check_collision(obstacle):
    car_radius = max(car_width, car_length)/2 * 0.85
    obs_radius = 0.9
    # if jumping high enough, pass over
    if is_jumping and car_jump_height > 0.8:
        return False
    dx = car_x - obstacle.x
    dz = car_z - obstacle.z
    return math.sqrt(dx*dx + dz*dz) < (car_radius + obs_radius)

# -----------------------
# Input handlers (unchanged)
# -----------------------
def key_down(key, x, y):
    if key in keys:
        keys[key] = True

def key_up(key, x, y):
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

# -----------------------
# Main (unchanged)
# -----------------------
def main():
    print("✨ Enhanced Beautiful Car Game (Optimized for Performance)")
    print("Controls: W/A/S/D accelerate/steer, Space = brake, J = jump, F = fire, 1 = boost, G/H = view, L = headlights, R = reset")
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1024, 768)
    glutInitWindowPosition(100, 100)
    glutCreateWindow(b"Enhanced Beautiful Car Game")
    init()
    reset_game()
    glutDisplayFunc(display)
    glutKeyboardFunc(key_down)
    glutKeyboardUpFunc(key_up)
    glutSpecialFunc(special_down)
    glutSpecialUpFunc(special_up)
    glutTimerFunc(16, update, 0)
    glutMainLoop()

if __name__ == "__main__":
    main()