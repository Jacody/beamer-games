import pygame
import math
import sys
import time
import random
import os  # Importieren für Pfade
import bot_logic

# --- Konstanten ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FIELD_COLOR = (34, 139, 34)
LINE_COLOR = (255, 255, 255)
TEXT_COLOR = (255, 255, 255)
HIGHLIGHT_COLOR = (255, 255, 0) # Gelb für Hervorhebung
DISABLED_COLOR = (100, 100, 100) # Grau für nicht wählbare Avatare
# Standardfarben (als Fallback, falls Bilder fehlen)
DEFAULT_P1_COLOR = (255, 0, 0)
DEFAULT_P2_COLOR = (0, 0, 255)
BALL_COLOR = (255, 255, 255)
TRIBUNE_COLOR = (60, 60, 60)

PLAYER_RADIUS = 15 # Wichtig für Kollisionen
BALL_RADIUS = 10
PLAYER_ROTATION_SPEED = 180
PLAYER_SPRINT_SPEED = 250
BALL_FRICTION = 0.90
BALL_KICK_MULTIPLIER = 1.1

GOAL_HEIGHT = SCREEN_HEIGHT / 3
GOAL_WIDTH = 10

TRIBUNE_HEIGHT = 50
NUM_SPECTATORS = 200
SPECTATOR_RADIUS = 3
SPECTATOR_COLORS = [
    (200, 0, 0), (0, 0, 200), (200, 200, 0), (0, 200, 0),
    (200, 100, 0), (150, 0, 150), (100, 100, 100), (255, 150, 150),
    (150, 150, 255), (255, 255, 150)
]

FPS = 60
GAME_DURATION = 120
RESET_DELAY = 1.5

# --- SPIELZUSTÄNDE ---
STATE_AVATAR_SELECT = "AVATAR_SELECT"
STATE_MENU = "MENU"
STATE_PLAYING = "PLAYING"
STATE_GOAL_PAUSE = "GOAL_PAUSE"
STATE_GAME_OVER = "GAME_OVER"

# --- AVATAR KONSTANTEN & DATEN ---
# --- NEU: Liste der Bilddateinamen ---
AVATAR_IMAGE_FILES = [
    "Smiling Emoji with Eyes Opened.png", # Dein erstes Bild
    "Smirk Face Emoji.png",             # Dein zweites Bild
    # Füge hier bei Bedarf weitere Dateinamen hinzu
]
AVATAR_PATH = "assets" # Ordner für die Bilder
# ------------------------------------
AVATAR_DISPLAY_SIZE = PLAYER_RADIUS * 4 # Größere Vorschau im Menü
AVATAR_SPACING = AVATAR_DISPLAY_SIZE + 25

# --- Bot Konfiguration ---
PLAYER2_IS_BOT = False

# --- Partikel Klasse (bleibt gleich) ---
class Particle:
    def __init__(self, pos, vel, color, lifetime, radius_range=(1, 3), gravity=0):
        self.pos = pygame.Vector2(pos); self.vel = pygame.Vector2(vel)
        self.color = color; self.lifetime = lifetime; self.start_lifetime = lifetime
        self.radius = random.uniform(radius_range[0], radius_range[1])
        self.gravity = gravity
    def update(self, dt):
        self.vel.y += self.gravity * dt; self.pos += self.vel * dt; self.lifetime -= dt
    def draw(self, surface):
        current_radius_int = int(self.radius)
        if self.lifetime > 0 and current_radius_int >= 1:
            alpha = max(0, min(255, int(255 * (self.lifetime / self.start_lifetime))))
            try:
                temp_surf = pygame.Surface((current_radius_int*2, current_radius_int*2), pygame.SRCALPHA)
                draw_color = (*self.color[:3], alpha)
                pygame.draw.circle(temp_surf, draw_color, (current_radius_int, current_radius_int), current_radius_int)
                surface.blit(temp_surf, self.pos - pygame.Vector2(self.radius, self.radius))
            except (ValueError, TypeError): pass

particles = []
MAX_PARTICLES = 350
def emit_particles(count, pos, base_color, vel_range=(-50, 50), life_range=(0.2, 0.6), radius_range=(1, 3), gravity=0):
    if len(particles) > MAX_PARTICLES - count: return
    for _ in range(count):
        vel = pygame.Vector2(random.uniform(vel_range[0], vel_range[1]), random.uniform(vel_range[0], vel_range[1]))
        r_offset, g_offset, b_offset = random.randint(-30, 30), random.randint(-30, 30), random.randint(-30, 30)
        p_color = (max(0, min(255, base_color[0] + r_offset)), max(0, min(255, base_color[1] + g_offset)), max(0, min(255, base_color[2] + b_offset)))
        lifetime = random.uniform(life_range[0], life_range[1])
        particles.append(Particle(pos, vel, p_color, lifetime, radius_range, gravity))
def update_and_draw_particles(dt, surface):
    for i in range(len(particles) - 1, -1, -1):
        p = particles[i]; p.update(dt)
        if p.lifetime <= 0: particles.pop(i)
        else: p.draw(surface)

# --- Funktion zum Laden der Avatare ---
loaded_avatars = {} # Speichert die skalierten Bilder für den Spieler
loaded_display_avatars = {} # Speichert die skalierten Bilder für das Menü

def load_avatars():
    print("Loading avatars...")
    player_target_size = (PLAYER_RADIUS * 2, PLAYER_RADIUS * 2)
    display_target_size = (AVATAR_DISPLAY_SIZE, AVATAR_DISPLAY_SIZE)
    global AVATAR_IMAGE_FILES # Erlaube Änderung der globalen Liste bei Fehlern

    valid_avatar_files = [] # Temporäre Liste für erfolgreich geladene

    if not os.path.isdir(AVATAR_PATH):
        print(f"ERROR: Avatar directory '{AVATAR_PATH}' not found!")
        AVATAR_IMAGE_FILES = [] # Keine Avatare verfügbar
        return

    for filename in AVATAR_IMAGE_FILES:
        filepath = os.path.join(AVATAR_PATH, filename)
        try:
            image = pygame.image.load(filepath).convert_alpha()
            # Skaliert für Spieler
            scaled_player = pygame.transform.smoothscale(image, player_target_size)
            loaded_avatars[filename] = scaled_player
            # Skaliert für Menü
            scaled_display = pygame.transform.smoothscale(image, display_target_size)
            loaded_display_avatars[filename] = scaled_display
            print(f" - Loaded {filename}")
            valid_avatar_files.append(filename) # Füge zur gültigen Liste hinzu
        except pygame.error as e:
            print(f"ERROR loading avatar '{filepath}': {e}. Skipping this avatar.")

    AVATAR_IMAGE_FILES = valid_avatar_files # Überschreibe mit gültiger Liste
    if not AVATAR_IMAGE_FILES:
         print("ERROR: No avatar images could be loaded successfully! Check the 'assets' folder.")


# --- Klassen ---
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, start_avatar_id, control_key, start_angle):
        super().__init__()
        self.radius = PLAYER_RADIUS
        self.control_key = control_key
        self.avatar_id = None
        self.original_image = None
        self.image = None
        self.rect = None
        self.fallback_color = DEFAULT_P1_COLOR if control_key == pygame.K_a else DEFAULT_P2_COLOR
        self.set_avatar(start_avatar_id) # Initiales Avatar setzen

        self.pos = pygame.Vector2(x, y)
        if self.rect: self.rect.center = self.pos
        else: self.rect = pygame.Rect(0,0, self.radius*2, self.radius*2); self.rect.center = self.pos

        self.velocity = pygame.Vector2(0, 0); self.angle = start_angle
        self.is_sprinting = False
        self.rotation_speed = PLAYER_ROTATION_SPEED
        self.sprint_speed = PLAYER_SPRINT_SPEED
        self.sprint_particle_timer = 0

    def set_avatar(self, avatar_id):
        """Setzt das Bild des Spielers basierend auf der Avatar-ID (Dateiname)."""
        self.avatar_id = avatar_id
        player_surf = None

        if avatar_id and avatar_id in loaded_avatars: # Prüfe ob ID gültig und geladen
            player_surf = loaded_avatars[avatar_id].copy() # Kopie verwenden!
        else:
            # Fallback, wenn ID ungültig oder Bild fehlte
            #print(f"Warning: Avatar ID '{avatar_id}' not found for player. Using fallback color.")
            player_surf = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(player_surf, self.fallback_color, (self.radius, self.radius), self.radius)

        # Pfeil IMMER über das Avatar-Bild/Fallback zeichnen
        arrow_color = (0, 0, 0)
        arrow_start = (self.radius, self.radius)
        arrow_end = (self.radius * 2, self.radius)
        pygame.draw.line(player_surf, arrow_color, arrow_start, arrow_end, 3)

        self.original_image = player_surf # Das ist jetzt das Basisbild für Rotationen
        self.image = self.original_image.copy()
        self.rect = self.image.get_rect()
        if hasattr(self, 'pos') and self.pos: self.rect.center = self.pos

    def rotate(self, dt):
        if not self.original_image: return
        self.angle = (self.angle + self.rotation_speed * dt) % 360
        self.image = pygame.transform.rotate(self.original_image, -self.angle)
        if self.rect: # Nur zentrieren, wenn Rect existiert
            self.rect = self.image.get_rect(center=self.pos)

    def start_sprint(self): self.is_sprinting = True
    def stop_sprint(self): self.is_sprinting = False; self.velocity = pygame.Vector2(0, 0)

    def update(self, dt, keys):
        self.sprint_particle_timer -= dt
        if self.is_sprinting:
            rad_angle = math.radians(self.angle)
            direction = pygame.Vector2(math.cos(rad_angle), math.sin(rad_angle))
            self.velocity = direction * self.sprint_speed
            self.pos += self.velocity * dt
            # Sprint Partikel Effekt
            if self.sprint_particle_timer <= 0:
                particle_pos = self.pos - direction * self.radius
                particle_color = self.fallback_color # Verwende Fallback-Farbe
                emit_particles(1, particle_pos, particle_color, vel_range=(-30, 30), life_range=(0.25, 0.5), radius_range=(2, 4))
                self.sprint_particle_timer = 0.025
        else:
            self.rotate(dt)
            self.velocity = pygame.Vector2(0, 0)
        # Grenzen prüfen...
        field_top = TRIBUNE_HEIGHT; field_bottom = SCREEN_HEIGHT - TRIBUNE_HEIGHT
        field_left = 0; field_right = SCREEN_WIDTH
        if self.pos.x - self.radius < field_left: self.pos.x = field_left + self.radius
        if self.pos.x + self.radius > field_right: self.pos.x = field_right - self.radius
        if self.pos.y - self.radius < field_top: self.pos.y = field_top + self.radius
        if self.pos.y + self.radius > field_bottom: self.pos.y = field_bottom - self.radius
        if self.rect: self.rect.center = self.pos

    def reset(self, x, y, angle, start_avatar_id):
         self.set_avatar(start_avatar_id)
         field_center_y = TRIBUNE_HEIGHT + (SCREEN_HEIGHT - 2 * TRIBUNE_HEIGHT) / 2
         self.pos = pygame.Vector2(x, field_center_y)
         if self.rect: self.rect.center = self.pos
         self.angle = angle
         self.is_sprinting = False
         self.velocity = pygame.Vector2(0, 0)

# (Ball Klasse bleibt unverändert)
class Ball(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__(); self.original_image = pygame.Surface((BALL_RADIUS*2, BALL_RADIUS*2), pygame.SRCALPHA)
        pygame.draw.circle(self.original_image, BALL_COLOR, (BALL_RADIUS, BALL_RADIUS), BALL_RADIUS)
        self.image = self.original_image; self.rect = self.image.get_rect(center=(x, y))
        self.pos = pygame.Vector2(x, y); self.velocity = pygame.Vector2(0, 0)
        self.friction_factor = BALL_FRICTION; self.radius = BALL_RADIUS; self.trail_positions = []
    def apply_friction(self, dt):
        self.velocity *= (self.friction_factor ** dt)
        if self.velocity.length() < 0.5:
            self.velocity = pygame.Vector2(0, 0)
    def update(self, dt, *args, **kwargs):
        if self.velocity.length() > BALL_TRAIL_MIN_SPEED:
             if pygame.time.get_ticks() % 2 == 0:
                 self.trail_positions.append(self.pos.copy())
                 if len(self.trail_positions) > BALL_TRAIL_LENGTH:
                     self.trail_positions.pop(0)
        elif self.trail_positions:
             self.trail_positions.pop(0) # Remove one point if stopped but trail exists
        self.apply_friction(dt)
        self.pos += self.velocity * dt
        # Kollisionen mit Rändern und Toren
        field_top=TRIBUNE_HEIGHT; field_bottom=SCREEN_HEIGHT-TRIBUNE_HEIGHT; field_left=0; field_right=SCREEN_WIDTH
        field_height=field_bottom-field_top; goal_y_abs_start=field_top+(field_height/2-GOAL_HEIGHT/2); goal_y_abs_end=field_top+(field_height/2+GOAL_HEIGHT/2)
        if self.pos.x - self.radius < field_left and not (goal_y_abs_start < self.pos.y < goal_y_abs_end): self.pos.x = field_left + self.radius; self.velocity.x *= -1
        if self.pos.x + self.radius > field_right and not (goal_y_abs_start < self.pos.y < goal_y_abs_end): self.pos.x = field_right - self.radius; self.velocity.x *= -1
        if self.pos.y - self.radius < field_top: self.pos.y = field_top + self.radius; self.velocity.y *= -1
        if self.pos.y + self.radius > field_bottom: self.pos.y = field_bottom - self.radius; self.velocity.y *= -1
        if self.rect: self.rect.center = self.pos # Sicherstellen, dass rect existiert
    def reset(self):
         field_center_y=TRIBUNE_HEIGHT+(SCREEN_HEIGHT-2*TRIBUNE_HEIGHT)/2
         self.pos = pygame.Vector2(SCREEN_WIDTH/2, field_center_y)
         if self.rect:
             self.rect.center = self.pos
             self.velocity = pygame.Vector2(0, 0)
             self.trail_positions.clear()

# --- Spiel Initialisierung ---
pygame.init()
pygame.font.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Simple Soccer Game - Loading Avatars...")
clock = pygame.time.Clock()
main_font = pygame.font.Font(None, 50)
menu_font = pygame.font.Font(None, 60)
small_font = pygame.font.Font(None, 35)

# --- Avatare laden ---
load_avatars() # Muss vor Spielerstellung aufgerufen werden!
# -------------------

# --- Zuschauer generieren ---
spectator_positions_colors = [];
def generate_spectators():
    spectator_positions_colors.clear()
    top_tribune_rect = pygame.Rect(0, 0, SCREEN_WIDTH, TRIBUNE_HEIGHT)
    for _ in range(NUM_SPECTATORS // 2):
        pos = (random.randint(top_tribune_rect.left, top_tribune_rect.right), random.randint(top_tribune_rect.top, top_tribune_rect.bottom))
        color = random.choice(SPECTATOR_COLORS); spectator_positions_colors.append((pos, color))
    bottom_tribune_rect = pygame.Rect(0, SCREEN_HEIGHT - TRIBUNE_HEIGHT, SCREEN_WIDTH, TRIBUNE_HEIGHT)
    for _ in range(NUM_SPECTATORS // 2):
        pos = (random.randint(bottom_tribune_rect.left, bottom_tribune_rect.right), random.randint(bottom_tribune_rect.top, bottom_tribune_rect.bottom))
        color = random.choice(SPECTATOR_COLORS); spectator_positions_colors.append((pos, color))
generate_spectators()

# --- Spielobjekte erstellen ---
field_center_y = TRIBUNE_HEIGHT + (SCREEN_HEIGHT - 2 * TRIBUNE_HEIGHT) / 2
# Wähle Default-IDs aus der (möglicherweise modifizierten) Liste
default_p1_id = AVATAR_IMAGE_FILES[0] if AVATAR_IMAGE_FILES else None
default_p2_id = AVATAR_IMAGE_FILES[1 % len(AVATAR_IMAGE_FILES)] if AVATAR_IMAGE_FILES else None # Nimmt 2. oder 1.

if not default_p1_id: # Fallback, wenn GAR KEINE Avatare geladen wurden
    print("FATAL: No avatars available. Exiting.")
    pygame.quit()
    sys.exit()

player1 = Player(SCREEN_WIDTH * 0.25, field_center_y, default_p1_id, pygame.K_a, 0)
player2 = Player(SCREEN_WIDTH * 0.75, field_center_y, default_p2_id, pygame.K_l, 180)
ball = Ball(SCREEN_WIDTH / 2, field_center_y)
all_sprites = pygame.sprite.Group(player1, player2, ball)
players = pygame.sprite.Group(player1, player2)

# --- Spielzustand Variablen ---
score1 = 0; score2 = 0; game_state = STATE_AVATAR_SELECT; start_time = 0;
remaining_time = GAME_DURATION; last_goal_time = 0

# --- Avatar Auswahl Variablen ---
selecting_player = 1; p1_avatar_index = -1; p2_avatar_index = -1; current_highlighted_index = 0

# --- Hilfsfunktionen ---
def draw_tribunes_and_spectators():
    pygame.draw.rect(screen, TRIBUNE_COLOR, (0, 0, SCREEN_WIDTH, TRIBUNE_HEIGHT))
    pygame.draw.rect(screen, TRIBUNE_COLOR, (0, SCREEN_HEIGHT - TRIBUNE_HEIGHT, SCREEN_WIDTH, TRIBUNE_HEIGHT))
    for pos, color in spectator_positions_colors: pygame.draw.circle(screen, color, pos, SPECTATOR_RADIUS)

def draw_field():
    field_rect = pygame.Rect(0, TRIBUNE_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT - 2 * TRIBUNE_HEIGHT)
    pygame.draw.rect(screen, FIELD_COLOR, field_rect)
    field_top=TRIBUNE_HEIGHT; field_bottom=SCREEN_HEIGHT-TRIBUNE_HEIGHT; field_height=field_bottom-field_top
    field_center_x=SCREEN_WIDTH/2; field_center_y=field_top+field_height/2
    pygame.draw.line(screen,LINE_COLOR,(field_center_x, field_top),(field_center_x, field_bottom),2)
    pygame.draw.circle(screen,LINE_COLOR,(field_center_x, field_center_y),70,2)
    goal_y_abs_start=field_top+(field_height/2-GOAL_HEIGHT/2); goal_y_abs_end=field_top+(field_height/2+GOAL_HEIGHT/2)
    pygame.draw.line(screen,LINE_COLOR,(GOAL_WIDTH, goal_y_abs_start),(GOAL_WIDTH, goal_y_abs_end),5)
    pygame.draw.line(screen,LINE_COLOR,(SCREEN_WIDTH-GOAL_WIDTH, goal_y_abs_start),(SCREEN_WIDTH-GOAL_WIDTH, goal_y_abs_end),5)

def draw_text(text, font, x, y, color=TEXT_COLOR):
    text_surface = font.render(text, True, color); text_rect = text_surface.get_rect(center=(x, y)); screen.blit(text_surface, text_rect)

def draw_avatar_selection_screen():
    screen.fill(TRIBUNE_COLOR)
    title_text = f"Player {selecting_player} - Select Avatar"
    draw_text(title_text, menu_font, SCREEN_WIDTH / 2, 100)

    num_avatars = len(AVATAR_IMAGE_FILES)
    if num_avatars == 0:
        draw_text("No Avatars Loaded!", main_font, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        draw_text("Check 'assets' folder.", small_font, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 50)
        return

    total_width = num_avatars * AVATAR_SPACING - (AVATAR_SPACING - AVATAR_DISPLAY_SIZE)
    start_x = (SCREEN_WIDTH - total_width) / 2
    display_y = SCREEN_HEIGHT / 2

    for i, avatar_id in enumerate(AVATAR_IMAGE_FILES):
        center_x = start_x + i * AVATAR_SPACING + AVATAR_DISPLAY_SIZE / 2
        display_rect = pygame.Rect(0, 0, AVATAR_DISPLAY_SIZE, AVATAR_DISPLAY_SIZE)
        display_rect.center = (center_x, display_y)

        is_disabled = False
        other_player_selection = p2_avatar_index if selecting_player == 1 else p1_avatar_index
        if i == other_player_selection: is_disabled = True

        if avatar_id in loaded_display_avatars:
            avatar_surf = loaded_display_avatars[avatar_id].copy()
            if is_disabled:
                overlay = pygame.Surface(avatar_surf.get_size(), pygame.SRCALPHA); overlay.fill((*DISABLED_COLOR, 180)); avatar_surf.blit(overlay, (0,0))
            screen.blit(avatar_surf, display_rect.topleft)
        else: pygame.draw.circle(screen, DISABLED_COLOR if is_disabled else (150,150,150), display_rect.center, AVATAR_DISPLAY_SIZE // 2)

        if i == current_highlighted_index and not is_disabled:
            pygame.draw.rect(screen, HIGHLIGHT_COLOR, display_rect, 4)

    draw_text("Use Left/Right Arrows", small_font, SCREEN_WIDTH / 2, SCREEN_HEIGHT - 150)
    draw_text("Enter/Space to Confirm", small_font, SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100)
    draw_text("ESC: Quit", small_font, SCREEN_WIDTH / 2, SCREEN_HEIGHT - 50)

def reset_positions():
    avatar_id_list = AVATAR_IMAGE_FILES
    if not avatar_id_list: # Fallback wenn keine Avatare
        p1_id = None
        p2_id = None
    else:
        p1_id = avatar_id_list[p1_avatar_index] if p1_avatar_index != -1 and p1_avatar_index < len(avatar_id_list) else avatar_id_list[0]
        p2_id = avatar_id_list[p2_avatar_index] if p2_avatar_index != -1 and p2_avatar_index < len(avatar_id_list) else avatar_id_list[1 % len(avatar_id_list)]

    player1_start_x = SCREEN_WIDTH * 0.25; player2_start_x = SCREEN_WIDTH * 0.75
    field_center_y = TRIBUNE_HEIGHT + (SCREEN_HEIGHT - 2 * TRIBUNE_HEIGHT) / 2

    player1.reset(player1_start_x, field_center_y, 0, p1_id)
    player2.reset(player2_start_x, field_center_y, 180, p2_id)
    ball.reset()
    particles.clear()

def start_new_game():
    global score1, score2, start_time, remaining_time, last_goal_time
    score1 = 0; score2 = 0; start_time = time.time(); remaining_time = GAME_DURATION; last_goal_time = 0
    reset_positions()

def reset_avatar_selection():
    global selecting_player, p1_avatar_index, p2_avatar_index, current_highlighted_index
    selecting_player = 1; p1_avatar_index = -1; p2_avatar_index = -1; current_highlighted_index = 0

def draw_ball_trail(surface, trail, ball_radius):
    num_points = len(trail);
    if num_points < 2: return
    for i in range(num_points):
        pos = trail[i]; alpha = max(0, int(150 * (i / num_points))); radius = max(1, int(ball_radius * 0.8 * (i / num_points)))
        if radius >= 1:
            try:
                temp_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA); draw_color = (*BALL_COLOR[:3], alpha)
                pygame.draw.circle(temp_surf, draw_color, (radius, radius), radius); surface.blit(temp_surf, pos - pygame.Vector2(radius, radius))
            except (ValueError, TypeError): pass

# --- Haupt Game Loop ---
pygame.display.set_caption("Simple Soccer Game - Select Avatar") # Update Titel nach Laden
running = True
while running:
    dt = clock.tick(FPS) / 1000.0
    keys = pygame.key.get_pressed()

    # --- Event Handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: running = False
            if event.key == pygame.K_r: reset_avatar_selection(); game_state = STATE_AVATAR_SELECT; pygame.display.set_caption("Select Avatar")

            if game_state == STATE_AVATAR_SELECT:
                 if AVATAR_IMAGE_FILES: # Nur wenn Avatare da sind
                     other_player_selection = p2_avatar_index if selecting_player == 1 else p1_avatar_index
                     num_avatars = len(AVATAR_IMAGE_FILES)
                     if event.key == pygame.K_RIGHT:
                         start_index = current_highlighted_index
                         while True:
                             current_highlighted_index = (current_highlighted_index + 1) % num_avatars
                             if current_highlighted_index != other_player_selection:
                                 break
                             if current_highlighted_index == start_index:
                                 break # Prevent infinite loop if only one available
                     elif event.key == pygame.K_LEFT:
                         start_index = current_highlighted_index
                         while True:
                             current_highlighted_index = (current_highlighted_index - 1 + num_avatars) % num_avatars
                             if current_highlighted_index != other_player_selection:
                                 break
                             if current_highlighted_index == start_index:
                                 break # Prevent infinite loop
                     elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        if current_highlighted_index != other_player_selection:
                            if selecting_player == 1:
                                p1_avatar_index = current_highlighted_index; selecting_player = 2
                                current_highlighted_index = 0
                                while current_highlighted_index == p1_avatar_index and num_avatars > 1: # Verhindere Endlosschleife bei nur 2 Avataren
                                     current_highlighted_index = (current_highlighted_index + 1) % num_avatars
                            elif selecting_player == 2:
                                p2_avatar_index = current_highlighted_index
                                # Avatare final setzen
                                player1.set_avatar(AVATAR_IMAGE_FILES[p1_avatar_index])
                                player2.set_avatar(AVATAR_IMAGE_FILES[p2_avatar_index])
                                game_state = STATE_MENU; pygame.display.set_caption("Select Mode")

            elif game_state == STATE_MENU:
                if event.key == pygame.K_1:
                    PLAYER2_IS_BOT = False
                    start_new_game()
                    game_state = STATE_PLAYING
                    pygame.display.set_caption(f"{PLAYER_AVATARS.get(player1.avatar_id, {}).get('name', 'P1')} vs {PLAYER_AVATARS.get(player2.avatar_id, {}).get('name', 'P2')}")
                elif event.key == pygame.K_2:
                    PLAYER2_IS_BOT = True
                    start_new_game()
                    game_state = STATE_PLAYING
                    pygame.display.set_caption(f"{PLAYER_AVATARS.get(player1.avatar_id, {}).get('name', 'P1')} vs Bot 🤖")

            elif game_state == STATE_PLAYING:
                if event.key == player1.control_key: player1.start_sprint()
                if not PLAYER2_IS_BOT and event.key == player2.control_key: player2.start_sprint()

        if event.type == pygame.KEYUP:
            if game_state == STATE_PLAYING:
                if event.key == player1.control_key: player1.stop_sprint()
                if not PLAYER2_IS_BOT and event.key == player2.control_key: player2.stop_sprint()

    # --- Partikel Update ---
    update_and_draw_particles(dt, screen) # Zeichnet direkt

    # --- Spiel Logik ---
    if game_state == STATE_PLAYING:
        if PLAYER2_IS_BOT:
             target_goal_x = SCREEN_WIDTH - GOAL_WIDTH # Bot zielt auf rechtes Tor
             # Übergebe relevante Infos an Bot Logik
             bot_action = bot_logic.get_bot_action(player2, ball, target_goal_x, SCREEN_WIDTH, SCREEN_HEIGHT, TRIBUNE_HEIGHT, PLAYER_RADIUS, BALL_RADIUS)

             if bot_action['rotate']:
                 player2.rotate(dt) # Bot dreht sich kontinuierlich
             if bot_action['sprint']:
                 if not player2.is_sprinting: player2.start_sprint()
             else:
                 if player2.is_sprinting: player2.stop_sprint()

        all_sprites.update(dt, keys)
        # Kollisionen
        collided_players = pygame.sprite.spritecollide(ball, players, False, pygame.sprite.collide_circle)
        for player in collided_players:
            distance_vec=ball.pos-player.pos; distance=distance_vec.length()
            if distance==0: collision_normal=pygame.Vector2(1,0)
            else: collision_normal=distance_vec.normalize()
            if player.is_sprinting:
                kick_speed=player.sprint_speed*BALL_KICK_MULTIPLIER; ball.velocity=collision_normal*kick_speed
                emit_particles(8,ball.pos,(255,255,100),vel_range=(-80,80),life_range=(0.1,0.4),radius_range=(1,3))
            else: repel_speed=50; ball.velocity+=collision_normal*repel_speed; player.pos-=collision_normal*repel_speed*0.1*dt
            overlap=(player.radius+ball.radius)-distance
            if overlap>0.1: correction_vec=collision_normal*overlap; ball.pos+=correction_vec*0.51; player.pos-=correction_vec*0.5; ball.rect.center=ball.pos; player.rect.center=player.pos
        if pygame.sprite.collide_circle(player1,player2):
            dist_vec_p1_p2=player2.pos-player1.pos; dist_p1_p2=dist_vec_p1_p2.length()
            if dist_p1_p2<(player1.radius+player2.radius):
                if dist_p1_p2==0: correction_vec=pygame.Vector2(1,0)
                else: correction_vec=dist_vec_p1_p2.normalize()
                overlap=(player1.radius+player2.radius)-dist_p1_p2
                if overlap>0: player1.pos-=correction_vec*overlap/2; player2.pos+=correction_vec*overlap/2; player1.rect.center=player1.pos; player2.rect.center=player2.pos
        # Torerkennung
        goal_scored=False; field_top=TRIBUNE_HEIGHT; field_bottom=SCREEN_HEIGHT-TRIBUNE_HEIGHT; field_height=field_bottom-field_top; goal_y_abs_start=field_top+(field_height/2-GOAL_HEIGHT/2); goal_y_abs_end=field_top+(field_height/2+GOAL_HEIGHT/2); goal_scorer_color=None
        if ball.rect.right<GOAL_WIDTH and goal_y_abs_start<ball.pos.y<goal_y_abs_end: score2+=1; goal_scored=True; goal_scorer_color=player2.fallback_color # Use fallback for particles
        elif ball.rect.left>SCREEN_WIDTH-GOAL_WIDTH and goal_y_abs_start<ball.pos.y<goal_y_abs_end: score1+=1; goal_scored=True; goal_scorer_color=player1.fallback_color
        if goal_scored:
            game_state=STATE_GOAL_PAUSE; last_goal_time=time.time(); player1.stop_sprint(); player2.stop_sprint()
            for _ in range(50): pos_x=random.uniform(SCREEN_WIDTH*0.2,SCREEN_WIDTH*0.8); pos_y=random.uniform(TRIBUNE_HEIGHT,TRIBUNE_HEIGHT+30); confetti_color=random.choice(SPECTATOR_COLORS+[goal_scorer_color]*3); emit_particles(1,(pos_x,pos_y),confetti_color,vel_range=(-40,40),life_range=(1.0,2.5),radius_range=(3,6),gravity=60)
        # Timer
        if start_time>0: elapsed_time=time.time()-start_time; remaining_time=max(0,GAME_DURATION-elapsed_time); \
            if remaining_time==0: game_state=STATE_GAME_OVER; player1.stop_sprint(); player2.stop_sprint()
    elif game_state==STATE_GOAL_PAUSE:
        if time.time()-last_goal_time>RESET_DELAY: reset_positions(); game_state=STATE_PLAYING

    # --- Zeichnen ---
    screen.fill((0,0,0))
    if game_state == STATE_AVATAR_SELECT:
        draw_avatar_selection_screen()
    else:
        draw_tribunes_and_spectators()
        if game_state == STATE_MENU:
             draw_text("Wähle den Modus:", menu_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-100)
             draw_text("1 : Player vs Player", main_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
             draw_text("(Uses selected avatars)", small_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2+40)
             draw_text("2 : Player vs Bot", main_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2+100)
             draw_text("(P1 uses selected avatar)", small_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2+140)
             draw_text("R: Change Avatars / ESC: Quit", small_font, SCREEN_WIDTH/2, SCREEN_HEIGHT-50)
        elif game_state == STATE_PLAYING or game_state == STATE_GOAL_PAUSE or game_state == STATE_GAME_OVER:
            draw_field()
            draw_ball_trail(screen, ball.trail_positions, BALL_RADIUS)
            all_sprites.draw(screen)
            update_and_draw_particles(dt, screen) # Partikel über Spieler/Ball zeichnen
            score_text = f"P1: {score1} - P2: {score2}"; draw_text(score_text, main_font, SCREEN_WIDTH/2, TRIBUNE_HEIGHT/2, TEXT_COLOR)
            minutes=int(remaining_time//60); seconds=int(remaining_time%60); timer_text=f"{minutes:02}:{seconds:02}"; draw_text(timer_text, main_font, SCREEN_WIDTH-100, TRIBUNE_HEIGHT/2, TEXT_COLOR)
            if game_state == STATE_GOAL_PAUSE: draw_text("GOAL!", menu_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2, TEXT_COLOR)
            elif game_state == STATE_GAME_OVER:
                if score1 != score2:
                    winner_text = f"Player {1 if score1 > score2 else 2} wins!"
                else:
                    winner_text = "Draw!"
                draw_text("Game Over", menu_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-60, TEXT_COLOR)
                draw_text(winner_text, main_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-10, TEXT_COLOR)
                draw_text("Press R for Avatar Select", small_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2+40, TEXT_COLOR)
                draw_text("Press ESC to Quit", small_font, SCREEN_WIDTH/2, SCREEN_HEIGHT/2+70, TEXT_COLOR)

    pygame.display.flip()

# --- Spiel beenden ---
pygame.quit()
sys.exit()