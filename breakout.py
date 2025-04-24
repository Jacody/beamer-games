import pygame
import sys
import random

# --- Konstanten ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
PADDLE_WIDTH = 100
PADDLE_HEIGHT = 15
BALL_RADIUS = 10
BRICK_WIDTH = 75
BRICK_HEIGHT = 20
BRICK_ROWS = 5
BRICK_COLS = SCREEN_WIDTH // (BRICK_WIDTH + 5) # Spalten basierend auf Bildschirmbreite

# Farben (RGB)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (213, 50, 80)
ORANGE = (254, 150, 0)
YELLOW = (236, 240, 0)
GREEN = (0, 200, 110)
BLUE = (60, 135, 220)
PADDLE_COLOR = BLUE
BALL_COLOR = WHITE
BRICK_COLORS = [RED, ORANGE, YELLOW, GREEN, BLUE] # Farben pro Reihe

# Geschwindigkeiten
PADDLE_SPEED = 8
BALL_SPEED_X_INITIAL = 4 # Startgeschwindigkeit X
BALL_SPEED_Y_INITIAL = -4 # Startgeschwindigkeit Y (nach oben)

# --- Spiel Setup ---
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Breakout")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36) # Standard-Schriftart

# --- Spielobjekte ---

# Paddel (Schläger)
# pygame.Rect(left, top, width, height)
paddle_rect = pygame.Rect(SCREEN_WIDTH // 2 - PADDLE_WIDTH // 2,
                          SCREEN_HEIGHT - PADDLE_HEIGHT - 10,
                          PADDLE_WIDTH, PADDLE_HEIGHT)

# Ball
ball_rect = pygame.Rect(SCREEN_WIDTH // 2 - BALL_RADIUS,
                       paddle_rect.top - BALL_RADIUS * 2 - 5, # Start über dem Paddel
                       BALL_RADIUS * 2, BALL_RADIUS * 2)
ball_dx = random.choice([BALL_SPEED_X_INITIAL, -BALL_SPEED_X_INITIAL]) # Zufällige Startrichtung X
ball_dy = BALL_SPEED_Y_INITIAL

# Bricks (Ziegelsteine)
bricks = []
def create_bricks():
    bricks.clear() # Alte Bricks löschen, falls vorhanden (für Neustart)
    y_offset = 40 # Abstand vom oberen Rand
    for row in range(BRICK_ROWS):
        x_offset = 5 # Abstand vom linken Rand
        for col in range(BRICK_COLS):
            brick_x = x_offset + col * (BRICK_WIDTH + 5)
            brick_y = y_offset + row * (BRICK_HEIGHT + 5)
            brick_rect = pygame.Rect(brick_x, brick_y, BRICK_WIDTH, BRICK_HEIGHT)
            # Farbe basierend auf der Reihe zuweisen
            color_index = row % len(BRICK_COLORS)
            bricks.append({'rect': brick_rect, 'color': BRICK_COLORS[color_index]})
            x_offset += 0 # Kein zusätzlicher Offset hier nötig
        y_offset += 0 # Kein zusätzlicher Offset hier nötig

create_bricks() # Bricks initial erstellen

# Spielvariablen
score = 0
lives = 3
game_over = False
game_won = False
paused = False

# --- Spiel Loop ---
running = True
while running:
    # --- Event Handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: # Spiel mit ESC beenden
                 running = False
            if event.key == pygame.K_p: # Spiel pausieren/fortsetzen mit P
                 paused = not paused
            if (game_over or game_won) and event.key == pygame.K_RETURN: # Neustart mit Enter
                # Spiel zurücksetzen
                game_over = False
                game_won = False
                score = 0
                lives = 3
                paddle_rect.centerx = SCREEN_WIDTH // 2
                ball_rect.centerx = SCREEN_WIDTH // 2
                ball_rect.centery = paddle_rect.top - BALL_RADIUS * 2 - 5
                ball_dx = random.choice([BALL_SPEED_X_INITIAL, -BALL_SPEED_X_INITIAL])
                ball_dy = BALL_SPEED_Y_INITIAL
                create_bricks() # Bricks neu erstellen


    if paused or game_over or game_won:
         # Wenn pausiert, Game Over oder gewonnen, nur Events verarbeiten
         # und den entsprechenden Bildschirm anzeigen (siehe Drawing-Sektion)
         pass # Gehe direkt zum Zeichnen
    else:
        # --- Spiel Logik (nur wenn nicht pausiert/game over/won) ---

        # Paddel Bewegung
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and paddle_rect.left > 0:
            paddle_rect.x -= PADDLE_SPEED
        if keys[pygame.K_RIGHT] and paddle_rect.right < SCREEN_WIDTH:
            paddle_rect.x += PADDLE_SPEED

        # Ball Bewegung
        ball_rect.x += ball_dx
        ball_rect.y += ball_dy

        # Ball Kollision mit Wänden
        if ball_rect.left <= 0 or ball_rect.right >= SCREEN_WIDTH:
            ball_dx *= -1 # Richtung umkehren
        if ball_rect.top <= 0:
            ball_dy *= -1 # Richtung umkehren

        # Ball Kollision mit Boden (Leben verlieren)
        if ball_rect.bottom >= SCREEN_HEIGHT:
            lives -= 1
            if lives <= 0:
                game_over = True
            else:
                # Ball zurücksetzen über dem Paddel
                ball_rect.centerx = paddle_rect.centerx
                ball_rect.centery = paddle_rect.top - BALL_RADIUS - 5
                ball_dy = BALL_SPEED_Y_INITIAL # Wieder nach oben starten
                ball_dx = random.choice([BALL_SPEED_X_INITIAL, -BALL_SPEED_X_INITIAL]) # Zufällige X-Richtung
                pygame.time.wait(500) # Kurze Pause

        # Ball Kollision mit Paddel
        if ball_rect.colliderect(paddle_rect) and ball_dy > 0: # Nur abprallen, wenn Ball nach unten fliegt
            # Differenz berechnen, um den Abprallwinkel leicht zu ändern
            # diff = ball_rect.centerx - paddle_rect.centerx
            # ball_dx = diff * 0.1 # Beeinflusst die X-Richtung (kann angepasst werden)

            # Sicherstellen, dass dy negativ wird
            ball_dy *= -1
            # Verhindern, dass der Ball im Paddel "stecken bleibt"
            ball_rect.bottom = paddle_rect.top


        # Ball Kollision mit Bricks
        brick_hit_index = -1
        for i, brick_data in enumerate(bricks):
            brick_rect = brick_data['rect']
            if ball_rect.colliderect(brick_rect):
                brick_hit_index = i
                # Kollisionslogik (einfach: Y-Richtung umkehren)
                # Genauere Kollisionserkennung (wo hat der Ball getroffen?) ist komplexer
                ball_dy *= -1
                score += 10 # Punkte für getroffenen Brick
                break # Nur einen Brick pro Frame treffen

        if brick_hit_index != -1:
            del bricks[brick_hit_index] # Getroffenen Brick entfernen

        # Überprüfen, ob alle Bricks zerstört wurden
        if not bricks:
            game_won = True


    # --- Zeichnen ---
    screen.fill(BLACK) # Hintergrund löschen

    # Paddel zeichnen
    pygame.draw.rect(screen, PADDLE_COLOR, paddle_rect, border_radius=5)

    # Ball zeichnen
    pygame.draw.ellipse(screen, BALL_COLOR, ball_rect) # Ellipse für runden Ball

    # Bricks zeichnen
    for brick_data in bricks:
        pygame.draw.rect(screen, brick_data['color'], brick_data['rect'], border_radius=3)

    # Score und Leben anzeigen
    score_text = font.render(f"Score: {score}", True, WHITE)
    lives_text = font.render(f"Lives: {lives}", True, WHITE)
    screen.blit(score_text, (10, 10))
    screen.blit(lives_text, (SCREEN_WIDTH - lives_text.get_width() - 10, 10))

    # Pausen-, Game Over- oder Gewonnen-Bildschirm
    if paused:
        pause_text = font.render("PAUSED (Press P to continue)", True, YELLOW)
        text_rect = pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        screen.blit(pause_text, text_rect)
    elif game_over:
        go_text = font.render("GAME OVER!", True, RED)
        restart_text = font.render("Press ENTER to Restart", True, WHITE)
        go_rect = go_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        screen.blit(go_text, go_rect)
        screen.blit(restart_text, restart_rect)
    elif game_won:
        win_text = font.render("YOU WON!", True, GREEN)
        restart_text = font.render("Press ENTER to Restart", True, WHITE)
        win_rect = win_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        screen.blit(win_text, win_rect)
        screen.blit(restart_text, restart_rect)


    # Bildschirm aktualisieren
    pygame.display.flip()

    # Framerate begrenzen
    clock.tick(60) # 60 Frames pro Sekunde

# --- Spiel beenden ---
pygame.quit()
sys.exit() 