import pygame
import sys
import random
import math
import wave  # Für WAV-Datei-Erstellung
import numpy as np # Für Sound-Daten-Generierung
import os # Zum Prüfen, ob Dateien existieren

# --- Konstanten ---
# (Unverändert von der vorherigen Version)
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 600
PADDLE_WIDTH = 18
PADDLE_HEIGHT = 120
BALL_RADIUS = 10
BALL_SIZE = BALL_RADIUS * 2
DARK_BG = (15, 15, 30)
NEON_CYAN = (0, 255, 255)
NEON_MAGENTA = (255, 0, 255)
NEON_LIME = (50, 255, 50)
WHITE = (240, 240, 240)
GREY = (100, 100, 120)
PADDLE_A_COLOR = NEON_CYAN
PADDLE_B_COLOR = NEON_MAGENTA
BALL_COLOR_DEFAULT = WHITE
BALL_COLOR_HIT = NEON_LIME
LINE_COLOR = GREY
PARTICLE_COLORS = [NEON_CYAN, NEON_MAGENTA, NEON_LIME, WHITE]
PADDLE_SPEED = 8
BALL_SPEED_X_INITIAL = 6
BALL_SPEED_Y_INITIAL = 6
BALL_SPEED_INCREASE = 0.2
WINNING_SCORE = 5
FLASH_DURATION = 8
PARTICLE_LIFESPAN = 25
PARTICLE_SPEED_MIN = 1
PARTICLE_SPEED_MAX = 4
PADDLE_HIT_PARTICLES = 20
WALL_HIT_PARTICLES = 8
SCORE_PARTICLES = 40

# --- Sounddatei-Generator ---
def generate_wav(filename, duration_ms, frequency, amplitude=16000, framerate=44100, fade_ms=5):
    """Generiert eine einfache WAV-Datei mit einem Sinuston und Fade-in/out."""
    if os.path.exists(filename):
        print(f"Datei {filename} existiert bereits, wird nicht überschrieben.")
        return

    print(f"Generiere Sounddatei: {filename}...")
    n_samples = int(framerate * duration_ms / 1000.0)
    t = np.linspace(0, duration_ms / 1000.0, n_samples, endpoint=False)
    signal = amplitude * np.sin(2 * np.pi * frequency * t)

    # Einfaches lineares Fade-in/Fade-out, um Klicks zu vermeiden
    fade_samples = int(framerate * fade_ms / 1000.0)
    if n_samples > 2 * fade_samples:
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        signal[:fade_samples] *= fade_in
        signal[-fade_samples:] *= fade_out
    elif n_samples > 0: # Kurzer Sound, nur fade-in/out überlappend
         fade = np.linspace(0, 1, n_samples // 2)
         signal[:n_samples // 2] *= fade
         fade = np.linspace(1, 0, n_samples - n_samples // 2)
         signal[n_samples // 2:] *= fade


    # Konvertieren zu 16-bit PCM
    signal_int = np.clip(signal, -32767, 32767).astype(np.int16)
    signal_bytes = signal_int.tobytes()

    try:
        with wave.open(filename, 'w') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit (2 bytes)
            wf.setframerate(framerate)
            wf.setnframes(n_samples)
            wf.setcomptype('NONE', 'not compressed')
            wf.writeframes(signal_bytes)
        print(f"{filename} erfolgreich generiert.")
    except Exception as e:
        print(f"Fehler beim Generieren von {filename}: {e}")


# --- Sounddateien definieren und ggf. generieren ---
PADDLE_HIT_SOUND_FILE = "paddle_hit.wav"
WALL_HIT_SOUND_FILE = "wall_hit.wav"
SCORE_SOUND_FILE = "score.wav"

# Generiere die Sounds, wenn sie nicht existieren
# (Parameter können angepasst werden für anderen Klang)
generate_wav(PADDLE_HIT_SOUND_FILE, duration_ms=50, frequency=1200)
generate_wav(WALL_HIT_SOUND_FILE, duration_ms=60, frequency=600)
generate_wav(SCORE_SOUND_FILE, duration_ms=150, frequency=1000) # Etwas längerer Ton für Punkt


# --- Spiel Setup ---
pygame.init()

# Soundeffekte laden (nachdem sie potenziell generiert wurden)
sound_enabled = False
try:
    pygame.mixer.init()
    if os.path.exists(PADDLE_HIT_SOUND_FILE):
        hit_sound = pygame.mixer.Sound(PADDLE_HIT_SOUND_FILE)
    else: raise FileNotFoundError(f"{PADDLE_HIT_SOUND_FILE} nicht gefunden oder generiert.")

    if os.path.exists(WALL_HIT_SOUND_FILE):
        wall_sound = pygame.mixer.Sound(WALL_HIT_SOUND_FILE)
    else: raise FileNotFoundError(f"{WALL_HIT_SOUND_FILE} nicht gefunden oder generiert.")

    if os.path.exists(SCORE_SOUND_FILE):
        score_sound = pygame.mixer.Sound(SCORE_SOUND_FILE)
    else: raise FileNotFoundError(f"{SCORE_SOUND_FILE} nicht gefunden oder generiert.")

    sound_enabled = True
    print("Sounds erfolgreich geladen.")
    # Optional: Lautstärke anpassen
    # hit_sound.set_volume(0.6)
    # wall_sound.set_volume(0.5)
    # score_sound.set_volume(0.7)

except (pygame.error, FileNotFoundError) as e:
    print(f"Warnung: Sounds konnten nicht initialisiert/geladen werden: {e}")
    print("Spiel läuft ohne Sound.")
    hit_sound, wall_sound, score_sound = None, None, None # Sicherstellen, dass Variablen existieren


screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("PONG - Neon Edition (mit generierten Sounds)")
clock = pygame.time.Clock()
score_font = pygame.font.Font(None, 80)
message_font = pygame.font.Font(None, 50)

# --- Spielobjekte ---
# (Unverändert)
paddle_a = pygame.Rect(30, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2, PADDLE_WIDTH, PADDLE_HEIGHT)
paddle_b = pygame.Rect(SCREEN_WIDTH - PADDLE_WIDTH - 30, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2, PADDLE_WIDTH, PADDLE_HEIGHT)
ball = pygame.Rect(SCREEN_WIDTH // 2 - BALL_RADIUS, SCREEN_HEIGHT // 2 - BALL_RADIUS, BALL_SIZE, BALL_SIZE)
current_ball_speed_x = BALL_SPEED_X_INITIAL
current_ball_speed_y = BALL_SPEED_Y_INITIAL
ball_dx = current_ball_speed_x * random.choice((1, -1))
ball_dy = current_ball_speed_y * random.choice((1, -1))

# --- Spielvariablen ---
# (Unverändert)
score_a = 0
score_b = 0
game_over = False
winner = ""
paddle_a_flash_timer = 0
paddle_b_flash_timer = 0
ball_flash_timer = 0
particles = []

# --- Partikel Klasse ---
class Particle:
    def __init__(self, x, y, angle, speed, color, size, lifespan):
        self.x = x
        self.y = y
        self.dx = math.cos(angle) * speed * random.uniform(0.5, 1.2) # Leichte zufällige Geschw.
        self.dy = math.sin(angle) * speed * random.uniform(0.5, 1.2)
        self.color = color
        self.size = size
        self.lifespan = lifespan
        self.max_lifespan = lifespan # Für Transparenz-Berechnung

    def update(self):
        self.x += self.dx
        self.y += self.dy
        self.lifespan -= 1

        # Größe abhängig von Lebensdauer aktualisieren
        if self.lifespan > 0 and self.max_lifespan > 0:
            self.size = max(0, self.size * (self.lifespan / self.max_lifespan))
        else:
            self.size = 0


    def draw(self, surface):
        if self.lifespan > 0 and self.size >= 1: # Nur zeichnen, wenn sichtbar
            # Berechne Alpha (Transparenz) basierend auf Lebenszeit
            alpha = max(0, min(255, int(255 * (self.lifespan / self.max_lifespan)**0.5))) # **0.5 für sanfteres Ausblenden
            try:
                # Erstelle eine temporäre Surface für Transparenz
                radius = int(self.size)
                particle_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(particle_surf, (*self.color, alpha), (radius, radius), radius)
                surface.blit(particle_surf, (int(self.x - radius), int(self.y - radius)))
            except ValueError: # Kann passieren, wenn Alpha < 0 wird
                 pass # Einfach nicht zeichnen


# --- Hilfsfunktionen ---
# (Unverändert, außer Sound-Aufrufe)
def create_particles(x, y, base_color, count):
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX)
        color = random.choice([base_color] + PARTICLE_COLORS) if random.random() > 0.2 else base_color # Meistens Basisfarbe
        size = random.uniform(2, 6)
        particles.append(Particle(x, y, angle, speed, color, size, PARTICLE_LIFESPAN + random.randint(-5, 5))) # Leichte Varianz Lebensdauer


def ball_reset():
    global ball_dx, ball_dy, current_ball_speed_x, current_ball_speed_y
    ball.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    create_particles(ball.centerx, ball.centery, random.choice(PARTICLE_COLORS), SCORE_PARTICLES)
    if sound_enabled and score_sound:
        score_sound.play()

    pygame.time.wait(600)

    current_ball_speed_x = BALL_SPEED_X_INITIAL
    current_ball_speed_y = BALL_SPEED_Y_INITIAL
    ball_dx = current_ball_speed_x * random.choice((1, -1))
    ball_dy = current_ball_speed_y * random.choice((1, -1))


def draw_elements():
    global paddle_a_flash_timer, paddle_b_flash_timer, ball_flash_timer
    screen.fill(DARK_BG)
    mid_x = SCREEN_WIDTH // 2
    dash_length = 10
    gap_length = 8
    for y in range(0, SCREEN_HEIGHT, dash_length + gap_length):
         pygame.draw.line(screen, LINE_COLOR, (mid_x, y), (mid_x, y + dash_length), 3)

    # Partikel zeichnen
    for particle in particles:
        particle.draw(screen)

    # Paddel / Ball Farben (Flash)
    current_paddle_a_color = PADDLE_A_COLOR
    if paddle_a_flash_timer > 0:
        current_paddle_a_color = WHITE if paddle_a_flash_timer % 4 < 2 else PADDLE_A_COLOR
        paddle_a_flash_timer -= 1

    current_paddle_b_color = PADDLE_B_COLOR
    if paddle_b_flash_timer > 0:
        current_paddle_b_color = WHITE if paddle_b_flash_timer % 4 < 2 else PADDLE_B_COLOR
        paddle_b_flash_timer -= 1

    current_ball_color = BALL_COLOR_DEFAULT
    if ball_flash_timer > 0:
        current_ball_color = BALL_COLOR_HIT
        ball_flash_timer -= 1

    # Objekte zeichnen
    pygame.draw.rect(screen, current_paddle_a_color, paddle_a, border_radius=5)
    pygame.draw.rect(screen, current_paddle_b_color, paddle_b, border_radius=5)
    pygame.draw.ellipse(screen, current_ball_color, ball)
    inner_ball_rect = ball.inflate(-BALL_SIZE * 0.4, -BALL_SIZE * 0.4)
    pygame.draw.ellipse(screen, WHITE, inner_ball_rect)

    # Scores
    score_a_text = score_font.render(str(score_a), True, PADDLE_A_COLOR)
    score_b_text = score_font.render(str(score_b), True, PADDLE_B_COLOR)
    screen.blit(score_a_text, (SCREEN_WIDTH * 0.25, 20))
    screen.blit(score_b_text, (SCREEN_WIDTH * 0.75 - score_b_text.get_width(), 20))


# --- Spiel Loop ---
running = True
while running:
    # --- Event Handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                 running = False
            if game_over and event.key == pygame.K_RETURN:
                 score_a = 0
                 score_b = 0
                 game_over = False
                 winner = ""
                 paddle_a.centery = SCREEN_HEIGHT // 2
                 paddle_b.centery = SCREEN_HEIGHT // 2
                 particles.clear()
                 ball_reset() # Startet mit Sound & Partikeln

    # --- Spiel Logik (nur wenn nicht Game Over) ---
    if not game_over:
        # Paddel Bewegung
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w] and paddle_a.top > 0: paddle_a.y -= PADDLE_SPEED
        if keys[pygame.K_s] and paddle_a.bottom < SCREEN_HEIGHT: paddle_a.y += PADDLE_SPEED
        if keys[pygame.K_UP] and paddle_b.top > 0: paddle_b.y -= PADDLE_SPEED
        if keys[pygame.K_DOWN] and paddle_b.bottom < SCREEN_HEIGHT: paddle_b.y += PADDLE_SPEED

        # Ball Bewegung
        ball.x += ball_dx
        ball.y += ball_dy

        # Ball Kollision mit Wänden (Oben/Unten)
        if ball.top <= 0 or ball.bottom >= SCREEN_HEIGHT:
            ball_dy *= -1
            ball_flash_timer = FLASH_DURATION
            # Sicherstellen, dass der Treffpunkt für Partikel innerhalb des Screens liegt
            hit_y = max(BALL_RADIUS, min(SCREEN_HEIGHT - BALL_RADIUS, ball.centery))
            create_particles(ball.centerx, hit_y, BALL_COLOR_HIT, WALL_HIT_PARTICLES)
            if sound_enabled and wall_sound: wall_sound.play()
            if ball.top < 0: ball.top = 0
            if ball.bottom > SCREEN_HEIGHT: ball.bottom = SCREEN_HEIGHT

        # Ball Kollision mit Paddeln
        collision_tolerance = abs(ball_dx) * 1.1 if ball_dx != 0 else 10 # Dynamische Toleranz
        paddle_hit = False

        if paddle_a.colliderect(ball) and ball_dx < 0:
             if abs(paddle_a.right - ball.left) < collision_tolerance:
                 ball_dx *= -1
                 relative_intersect_y = (paddle_a.centery - ball.centery)
                 normalized_relative_intersect_y = relative_intersect_y / (PADDLE_HEIGHT / 2)
                 bounce_angle = normalized_relative_intersect_y * (math.pi / 3.5) # Etwas flacherer max Winkel
                 current_ball_speed_x = min(abs(current_ball_speed_x) + BALL_SPEED_INCREASE, 15) # Max Speed X
                 current_ball_speed_y = min(abs(current_ball_speed_y) + BALL_SPEED_INCREASE, 15) # Max Speed Y
                 ball_dx = current_ball_speed_x * math.cos(bounce_angle)
                 ball_dy = current_ball_speed_y * -math.sin(bounce_angle)
                 paddle_a_flash_timer = FLASH_DURATION
                 ball.left = paddle_a.right # Korrigiere Position
                 paddle_hit = True
                 create_particles(ball.midright[0], ball.centery, PADDLE_A_COLOR, PADDLE_HIT_PARTICLES)


        elif paddle_b.colliderect(ball) and ball_dx > 0:
            if abs(paddle_b.left - ball.right) < collision_tolerance:
                ball_dx *= -1
                relative_intersect_y = (paddle_b.centery - ball.centery)
                normalized_relative_intersect_y = relative_intersect_y / (PADDLE_HEIGHT / 2)
                bounce_angle = normalized_relative_intersect_y * (math.pi / 3.5)
                current_ball_speed_x = min(abs(current_ball_speed_x) + BALL_SPEED_INCREASE, 15)
                current_ball_speed_y = min(abs(current_ball_speed_y) + BALL_SPEED_INCREASE, 15)
                ball_dx = current_ball_speed_x * -math.cos(bounce_angle)
                ball_dy = current_ball_speed_y * -math.sin(bounce_angle)
                paddle_b_flash_timer = FLASH_DURATION
                ball.right = paddle_b.left # Korrigiere Position
                paddle_hit = True
                create_particles(ball.midleft[0], ball.centery, PADDLE_B_COLOR, PADDLE_HIT_PARTICLES)

        if paddle_hit:
            ball_flash_timer = FLASH_DURATION
            if sound_enabled and hit_sound: hit_sound.play()


        # Ball aus dem Spielfeld (Punkt für Gegner)
        scored = False
        if ball.left <= -BALL_SIZE: # Etwas Toleranz, damit Reset nicht zu früh ist
            score_b += 1
            scored = True
            if score_b >= WINNING_SCORE:
                game_over = True
                winner = "Player Magenta"
        elif ball.right >= SCREEN_WIDTH + BALL_SIZE:
            score_a += 1
            scored = True
            if score_a >= WINNING_SCORE:
                game_over = True
                winner = "Player Cyan"

        if scored and not game_over:
            ball_reset()


    # --- Partikel Logik ---
    live_particles = []
    for p in particles:
        p.update()
        if p.lifespan > 0:
            live_particles.append(p)
    particles = live_particles


    # --- Zeichnen ---
    draw_elements()

    # Game Over Bildschirm
    if game_over:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        win_text_surface = score_font.render(f"{winner} Wins!", True, WHITE)
        restart_text_surface = message_font.render("Press ENTER to Restart", True, GREY)
        win_rect = win_text_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        restart_rect = restart_text_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
        screen.blit(win_text_surface, win_rect)
        screen.blit(restart_text_surface, restart_rect)


    # Bildschirm aktualisieren
    pygame.display.flip()

    # Framerate begrenzen
    clock.tick(60)

# --- Spiel beenden ---
pygame.quit()
sys.exit()