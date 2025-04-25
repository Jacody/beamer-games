# bot_logic.py

import pygame
import math

# --- Bot spezifische Konstanten ---
BOT_ANGLE_TOLERANCE_FAR = 35   # Toleranz, wenn weit weg
BOT_ANGLE_TOLERANCE_NEAR = 20  # Toleranz, wenn nah dran (für Positionierung)
BOT_ANGLE_TOLERANCE_SHOOTING = 10 # Sehr präzise Ausrichtung für den Schuss selbst
BOT_KICK_DISTANCE_FACTOR = 1.2 # Leicht erhöht, um "nah" etwas früher zu erkennen
BOT_WALL_AVOID_DISTANCE = 20   # Vorausschau für Wandvermeidung
WALL_TOUCH_TOLERANCE = 1.0     # Toleranz für Wandberührung

# --- Hilfsfunktionen ---

def angle_difference(angle1, angle2):
    """ Berechnet die kürzeste Differenz zwischen zwei Winkeln (-180 bis 180). """
    a1 = angle1 % 360
    a2 = angle2 % 360
    diff = a2 - a1
    if diff > 180: diff -= 360
    elif diff <= -180: diff += 360
    return diff

def is_touching_wall(bot_pos, bot_radius, screen_width, screen_height, tribune_height):
    """ Prüft, ob der Bot sehr nah an einer Wand ist. """
    field_top = tribune_height
    field_bottom = screen_height - tribune_height
    field_left = 0
    field_right = screen_width
    
    if bot_pos.x - bot_radius <= field_left + WALL_TOUCH_TOLERANCE: return True
    if bot_pos.x + bot_radius >= field_right - WALL_TOUCH_TOLERANCE: return True
    if bot_pos.y - bot_radius <= field_top + WALL_TOUCH_TOLERANCE: return True
    if bot_pos.y + bot_radius >= field_bottom - WALL_TOUCH_TOLERANCE: return True
    return False

def check_wall_collision_imminent(bot_pos, bot_angle, bot_radius, look_ahead_distance, screen_width, screen_height, tribune_height):
    """ Prüft, ob ein Sprint zur Wandkollision führt. """
    if look_ahead_distance <= 0: return False
    rad_angle = math.radians(bot_angle)
    try: 
        direction = pygame.Vector2(math.cos(rad_angle), math.sin(rad_angle)).normalize()
    except ValueError: 
        direction = pygame.Vector2(1, 0)
    
    projected_pos = bot_pos + direction * look_ahead_distance
    field_top = tribune_height
    field_bottom = screen_height - tribune_height
    field_left = 0
    field_right = screen_width
    
    if projected_pos.x - bot_radius < field_left: return True
    if projected_pos.x + bot_radius > field_right: return True
    if projected_pos.y - bot_radius < field_top: return True
    if projected_pos.y + bot_radius > field_bottom: return True
    return False

# --- HAUPTFUNKTION (Mit Schusslogik) ---
def get_bot_decision(bot_player, ball, target_goal_center_x, screen_width, screen_height, player_radius, ball_radius, tribune_height):
    """
    Entscheidet, ob der Bot sprinten soll.
    Priorisiert das Schießen, wenn in Position.
    """
    kick_distance_threshold = (player_radius + ball_radius) * BOT_KICK_DISTANCE_FACTOR

    # --- Priorisierte Wandberührungsprüfung ---
    touching_wall = is_touching_wall(bot_player.pos, player_radius, screen_width, screen_height, tribune_height)
    if touching_wall:
        return False # An Wand: Nicht sprinten

    # --- Vektoren und Distanzen ---
    bot_to_ball_vec = ball.pos - bot_player.pos
    bot_to_ball_dist = bot_to_ball_vec.length() if bot_to_ball_vec.length() > 0 else 1
    is_near_ball = bot_to_ball_dist < kick_distance_threshold

    # --- Spielfeldmitte ---
    field_center_y = tribune_height + (screen_height - 2 * tribune_height) / 2

    # --- Ermittle, ob der Bot HINTER dem Ball ist (relativ zum Ziel) ---
    # Annahme: Bot ist Player 2, attackiert nach links (target_goal_center_x ist klein, nahe 0)
    is_behind_ball = False
    if target_goal_center_x < screen_width / 2: # Angreifen nach links
        # Bot muss rechts vom Ball sein (größere X-Koordinate)
        is_behind_ball = bot_player.pos.x > ball.pos.x + ball_radius * 0.5
    else: # Angreifen nach rechts
        # Bot muss links vom Ball sein (kleinere X-Koordinate)
        is_behind_ball = bot_player.pos.x < ball.pos.x - ball_radius * 0.5

    # --- Defensive Überlegung ---
    should_play_defensive = False
    own_goal_center_x = screen_width - target_goal_center_x
    if abs(ball.pos.x - own_goal_center_x) < screen_width * 0.20 and bot_to_ball_dist < kick_distance_threshold * 1.5:
         should_play_defensive = True

    # --- Zielbestimmung ---
    target_pos = None

    if should_play_defensive:
        # Höchste Priorität: Verteidigen, wenn Ball nah am eigenen Tor
        target_pos = pygame.Vector2(screen_width / 2, ball.pos.y) # Zur Mitte spielen
    elif is_near_ball and is_behind_ball:
        # Zweithöchste Priorität: Schießen, wenn nah und hinter dem Ball
        target_pos = ball.pos # Direkt auf den Ball zielen
    elif is_near_ball:
        # Dritthöchste Priorität: Nah am Ball, aber nicht optimal zum Schießen
        target_pos = pygame.Vector2(target_goal_center_x, field_center_y)
    else:
        # Niedrigste Priorität: Weit vom Ball -> Ball verfolgen
        target_pos = ball.pos

    # Y-Grenzen für Ziel anpassen (wenn Ziel gesetzt)
    if target_pos:
        target_pos.y = max(tribune_height + player_radius, min(screen_height - tribune_height - player_radius, target_pos.y))
    else:
        # Sollte nicht passieren, aber als Fallback
        return False

    # --- Winkelberechnung ---
    bot_to_target_vec = target_pos - bot_player.pos
    if bot_to_target_vec.length_squared() < 1e-6:
        return False # Kein klares Ziel

    try: 
        target_angle = pygame.Vector2(1, 0).angle_to(bot_to_target_vec)
    except ValueError: 
        return False

    current_angle = bot_player.angle
    diff = angle_difference(current_angle, target_angle)

    # --- Sprintentscheidung ---
    shooting_mode = (is_near_ball and is_behind_ball and not should_play_defensive)
    current_angle_tolerance = BOT_ANGLE_TOLERANCE_SHOOTING if shooting_mode else \
                              (BOT_ANGLE_TOLERANCE_NEAR if is_near_ball else BOT_ANGLE_TOLERANCE_FAR)

    # Bedingung 1: Passt der Winkel?
    if abs(diff) < current_angle_tolerance:
        # Bedingung 2: Droht Wandkollision?
        if check_wall_collision_imminent(
            bot_player.pos, bot_player.angle, player_radius,
            BOT_WALL_AVOID_DISTANCE, screen_width, screen_height, tribune_height
        ):
            return False # Wand im Weg
        else:
            # Winkel passt, keine Wand -> SPRINT!
            return True
    else:
        # Winkel passt nicht -> Nur drehen
        return False