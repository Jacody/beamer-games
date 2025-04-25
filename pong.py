import pygame
import sys
import random
import math # Für Partikel-Winkel

# --- Konstanten ---
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 600
PADDLE_WIDTH = 18
PADDLE_HEIGHT = 120
BALL_RADIUS = 10 # Radius für Zeichnung, Rechteck bleibt quadratisch
BALL_SIZE = BALL_RADIUS * 2

# Farben (RGB) - Mehr Neon/Vibrant
DARK_BG = (15, 15, 30)      # Dunkelblau/Violett Hintergrund
NEON_CYAN = (0, 255, 255)
NEON_MAGENTA = (255, 0, 255)
NEON_LIME = (50, 255, 50)
WHITE = (240, 240, 240)     # Leicht gedämpftes Weiß
GREY = (100, 100, 120)      # Für die Mittellinie

PADDLE_A_COLOR = NEON_CYAN
PADDLE_B_COLOR = NEON_MAGENTA
BALL_COLOR_DEFAULT = WHITE
BALL_COLOR_HIT = NEON_LIME
LINE_COLOR = GREY
PARTICLE_COLORS = [NEON_CYAN, NEON_MAGENTA, NEON_LIME, WHITE]

# Geschwindigkeiten
PADDLE_SPEED = 8
BALL_SPEED_X_INITIAL = 6
BALL_SPEED_Y_INITIAL = 6
BALL_SPEED_INCREASE = 0.2 # Erhöhung bei jedem Paddel-Treffer

# Punkte-Limit
WINNING_SCORE = 5

# Effekt-Konstanten
FLASH_DURATION = 8 # Frames, die ein Objekt nach Treffer blinkt
PARTICLE_LIFESPAN = 25
PARTICLE_SPEED_MIN = 1
PARTICLE_SPEED_MAX = 4
PADDLE_HIT_PARTICLES = 20
WALL_HIT_PARTICLES = 8
SCORE_PARTICLES = 40

# --- Spiel Setup ---
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("PONG - Neon Edition")
clock = pygame.time.Clock()
score_font = pygame.font.Font(None, 80) # Größere Schrift für den Score
message_font = pygame.font.Font(None, 50) # Kleinere Schrift für Nachrichten

# Soundeffekte (Optional, aber verbessert das Gefühl)
try:
    pygame.mixer.init()
    hit_sound = pygame.mixer.Sound("paddle_hit.wav") # Erstelle/finde .wav Dateien
    wall_sound = pygame.mixer.Sound("wall_hit.wav")
    score_sound = pygame.mixer.Sound("score.wav")
    # Lautstärke anpassen falls nötig
    # hit_sound.set_volume(0.5)
    # wall_sound.set_volume(0.5)
    # score_sound.set_volume(0.7)
    sound_enabled = True
except pygame.error:
    print("Warnung: Sounddateien nicht gefunden oder Mixer konnte nicht initialisiert werden.")
    sound_enabled = False


# --- Spielobjekte ---

# Paddel
paddle_a = pygame.Rect(30, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2, PADDLE_WIDTH, PADDLE_HEIGHT)
paddle_b = pygame.Rect(SCREEN_WIDTH - PADDLE_WIDTH - 30, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2, PADDLE_WIDTH, PADDLE_HEIGHT)

# Ball
ball = pygame.Rect(SCREEN_WIDTH // 2 - BALL_RADIUS, SCREEN_HEIGHT // 2 - BALL_RADIUS, BALL_SIZE, BALL_SIZE)

# Ballgeschwindigkeit
current_ball_speed_x = BALL_SPEED_X_INITIAL
current_ball_speed_y = BALL_SPEED_Y_INITIAL
ball_dx = current_ball_speed_x * random.choice((1, -1))
ball_dy = current_ball_speed_y * random.choice((1, -1))

# --- Spielvariablen ---
score_a = 0
score_b = 0
game_over = False
winner = ""

# Effekt-Variablen
paddle_a_flash_timer = 0
paddle_b_flash_timer = 0
ball_flash_timer = 0
particles = [] # Liste für Partikel-Objekte

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
        self.size = max(0, self.size - (self.max_lifespan / self.lifespan) * 0.05) # Werden kleiner

    def draw(self, surface):
        if self.lifespan > 0 and self.size > 0:
            # Berechne Alpha (Transparenz) basierend auf Lebenszeit
            alpha = max(0, min(255, int(255 * (self.lifespan / self.max_lifespan))))
            # Erstelle eine temporäre Surface für Transparenz
            particle_surf = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
            pygame.draw.circle(particle_surf, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
            surface.blit(particle_surf, (int(self.x - self.size), int(self.y - self.size)))
            # Alternative (einfacher, ohne Transparenz):
            # pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.size))

# --- Hilfsfunktionen ---
def create_particles(x, y, base_color, count):
    """Erzeugt Partikel an einer Position."""
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi) # Zufälliger Winkel
        speed = random.uniform(PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX)
        # Wähle eine Farbe aus der Palette oder der Basisfarbe
        color = random.choice([base_color] + PARTICLE_COLORS)
        size = random.uniform(2, 5)
        particles.append(Particle(x, y, angle, speed, color, size, PARTICLE_LIFESPAN))

def ball_reset():
    """Setzt den Ball zurück und erzeugt Partikeleffekt."""
    global ball_dx, ball_dy, current_ball_speed_x, current_ball_speed_y
    ball.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    # Partikel in der Mitte
    create_particles(ball.centerx, ball.centery, random.choice(PARTICLE_COLORS), SCORE_PARTICLES)

    pygame.time.wait(600) # Längere Pause nach Punkt für den Effekt

    # Reset Geschwindigkeiten und wähle zufällige Richtung
    current_ball_speed_x = BALL_SPEED_X_INITIAL
    current_ball_speed_y = BALL_SPEED_Y_INITIAL
    ball_dx = current_ball_speed_x * random.choice((1, -1))
    ball_dy = current_ball_speed_y * random.choice((1, -1))
    if sound_enabled:
        score_sound.play()


def draw_elements():
    """Zeichnet alle Spielelemente mit Effekten."""
    global paddle_a_flash_timer, paddle_b_flash_timer, ball_flash_timer

    # Hintergrund (könnte auch ein Gradient sein)
    screen.fill(DARK_BG)

    # Mittellinie (dezenter)
    mid_x = SCREEN_WIDTH // 2
    dash_length = 10
    gap_length = 8
    for y in range(0, SCREEN_HEIGHT, dash_length + gap_length):
         pygame.draw.line(screen, LINE_COLOR, (mid_x, y), (mid_x, y + dash_length), 3)

    # Partikel zeichnen (unter den anderen Elementen)
    for particle in particles:
        particle.draw(screen)

    # Paddel A Farbe bestimmen (Flash-Effekt)
    current_paddle_a_color = PADDLE_A_COLOR
    if paddle_a_flash_timer > 0:
        if paddle_a_flash_timer % 4 < 2: # Lässt es blinken
            current_paddle_a_color = WHITE
        paddle_a_flash_timer -= 1

    # Paddel B Farbe bestimmen
    current_paddle_b_color = PADDLE_B_COLOR
    if paddle_b_flash_timer > 0:
        if paddle_b_flash_timer % 4 < 2:
            current_paddle_b_color = WHITE
        paddle_b_flash_timer -= 1

    # Ball Farbe bestimmen
    current_ball_color = BALL_COLOR_DEFAULT
    if ball_flash_timer > 0:
        current_ball_color = BALL_COLOR_HIT
        ball_flash_timer -= 1

    # Paddel zeichnen (mit abgerundeten Ecken)
    pygame.draw.rect(screen, current_paddle_a_color, paddle_a, border_radius=5)
    pygame.draw.rect(screen, current_paddle_b_color, paddle_b, border_radius=5)

    # Ball zeichnen (als Kreis)
    pygame.draw.ellipse(screen, current_ball_color, ball)
    # Optional: Kleinerer weißer Kern für Glüheffekt-Andeutung
    inner_ball_rect = ball.inflate(-BALL_SIZE * 0.4, -BALL_SIZE * 0.4)
    pygame.draw.ellipse(screen, WHITE, inner_ball_rect)


    # Scores
    score_a_text = score_font.render(str(score_a), True, PADDLE_A_COLOR)
    score_b_text = score_font.render(str(score_b), True, PADDLE_B_COLOR)
    screen.blit(score_a_text, (SCREEN_WIDTH * 0.25, 20)) # Etwas mehr zur Mitte
    screen.blit(score_b_text, (SCREEN_WIDTH * 0.75 - score_b_text.get_width(), 20)) # Etwas mehr zur Mitte


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
                 # Spiel neu starten
                 score_a = 0
                 score_b = 0
                 game_over = False
                 winner = ""
                 paddle_a.centery = SCREEN_HEIGHT // 2
                 paddle_b.centery = SCREEN_HEIGHT // 2
                 particles.clear() # Partikel vom Game Over entfernen
                 ball_reset()


    # --- Spiel Logik (nur wenn nicht Game Over) ---
    if not game_over:
        # Paddel Bewegung
        keys = pygame.key.get_pressed()
        # Spieler A (Links: W/S)
        if keys[pygame.K_w] and paddle_a.top > 0:
            paddle_a.y -= PADDLE_SPEED
        if keys[pygame.K_s] and paddle_a.bottom < SCREEN_HEIGHT:
            paddle_a.y += PADDLE_SPEED
        # Spieler B (Rechts: Pfeil Hoch/Runter)
        if keys[pygame.K_UP] and paddle_b.top > 0:
            paddle_b.y -= PADDLE_SPEED
        if keys[pygame.K_DOWN] and paddle_b.bottom < SCREEN_HEIGHT:
            paddle_b.y += PADDLE_SPEED

        # Ball Bewegung
        ball.x += ball_dx
        ball.y += ball_dy

        # Ball Kollision mit Wänden (Oben/Unten)
        if ball.top <= 0 or ball.bottom >= SCREEN_HEIGHT:
            ball_dy *= -1
            ball_flash_timer = FLASH_DURATION # Ball blinken lassen
            create_particles(ball.centerx, ball.centery, BALL_COLOR_HIT, WALL_HIT_PARTICLES) # Partikel an Wand
            if sound_enabled:
                wall_sound.play()
             # Verhindern, dass der Ball stecken bleibt
            if ball.top < 0: ball.top = 0
            if ball.bottom > SCREEN_HEIGHT: ball.bottom = SCREEN_HEIGHT


        # Ball Kollision mit Paddeln
        collision_tolerance = 10 # Toleranz, um "durchrutschen" zu vermeiden
        if ball.colliderect(paddle_a) and ball_dx < 0:
             if abs(paddle_a.right - ball.left) < collision_tolerance:
                 ball_dx *= -1
                 # Winkel basierend auf Treffpunkt am Paddel anpassen
                 relative_intersect_y = (paddle_a.centery - ball.centery)
                 normalized_relative_intersect_y = relative_intersect_y / (PADDLE_HEIGHT / 2)
                 bounce_angle = normalized_relative_intersect_y * (math.pi / 3) # Max 60 Grad
                 # Geschwindigkeit erhöhen
                 current_ball_speed_x += BALL_SPEED_INCREASE
                 current_ball_speed_y += BALL_SPEED_INCREASE
                 ball_dx = current_ball_speed_x * math.cos(bounce_angle)
                 ball_dy = current_ball_speed_y * -math.sin(bounce_angle)

                 paddle_a_flash_timer = FLASH_DURATION # Paddel A blinken
                 ball_flash_timer = FLASH_DURATION     # Ball blinken
                 create_particles(ball.centerx, ball.centery, PADDLE_A_COLOR, PADDLE_HIT_PARTICLES) # Partikel
                 if sound_enabled: hit_sound.play()
                 # Verhindern, dass Ball im Paddel steckt
                 ball.left = paddle_a.right


        if ball.colliderect(paddle_b) and ball_dx > 0:
            if abs(paddle_b.left - ball.right) < collision_tolerance:
                ball_dx *= -1
                relative_intersect_y = (paddle_b.centery - ball.centery)
                normalized_relative_intersect_y = relative_intersect_y / (PADDLE_HEIGHT / 2)
                bounce_angle = normalized_relative_intersect_y * (math.pi / 3) # Max 60 Grad
                current_ball_speed_x += BALL_SPEED_INCREASE
                current_ball_speed_y += BALL_SPEED_INCREASE
                # Winkel spiegeln für rechtes Paddel
                ball_dx = current_ball_speed_x * -math.cos(bounce_angle)
                ball_dy = current_ball_speed_y * -math.sin(bounce_angle)

                paddle_b_flash_timer = FLASH_DURATION # Paddel B blinken
                ball_flash_timer = FLASH_DURATION     # Ball blinken
                create_particles(ball.centerx, ball.centery, PADDLE_B_COLOR, PADDLE_HIT_PARTICLES) # Partikel
                if sound_enabled: hit_sound.play()
                # Verhindern, dass Ball im Paddel steckt
                ball.right = paddle_b.left


        # Ball aus dem Spielfeld (Punkt für Gegner)
        if ball.left <= 0:
            score_b += 1
            if score_b >= WINNING_SCORE:
                game_over = True
                winner = "Player Magenta" # Spieler B
            else:
                ball_reset()
        if ball.right >= SCREEN_WIDTH:
            score_a += 1
            if score_a >= WINNING_SCORE:
                game_over = True
                winner = "Player Cyan" # Spieler A
            else:
                ball_reset()


    # --- Partikel Logik ---
    # Update Partikel Positionen und Lebensdauer
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
        # Verdunkelter Hintergrund für bessere Lesbarkeit
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180)) # Schwarz mit Transparenz
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
    clock.tick(60) # 60 Frames pro Sekunde

# --- Spiel beenden ---
pygame.quit()
sys.exit()