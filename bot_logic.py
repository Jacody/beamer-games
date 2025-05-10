# bot_logic.py

import pygame
import math
import time

# --- Modul-globale Variablen für den Bot-Zustand ---
_bot_current_mode = "ATTACK"  # <<<<<<< HIER ÄNDERN: Startmodus ist jetzt ATTACK
_bot_mode_timer = 0.0

# --- Bot Konstanten ---
# Zeitsteuerung für Moduswechsel
BOT_DEFENSE_DURATION = 10.0  # Sekunden im Verteidigungsmodus
BOT_ATTACK_DURATION = 10.0   # <<<<<<< HIER ÄNDERN: Sekunden im Angriffsmodus

# Allgemeine Bewegung
BOT_GOTO_ANGLE_TOLERANCE = 15
BOT_GOTO_DISTANCE_TOLERANCE = 20

# Defensivmodus
BOT_DEFENSE_X_LINE_OFFSET = 70
BOT_DEFENSE_MAX_Y_DEVIATION_FROM_GOAL_CENTER = 150

# Angriffsmodus
BOT_ATTACK_TARGET_DEPTH_FACTOR = 1.5
BOT_ATTACK_KICK_ANGLE_TOLERANCE = 8
BOT_ATTACK_MIN_DIST_TO_BALL_FOR_TARGET_BEHIND = 40

# --- Hilfsfunktionen (angle_difference bleibt gleich) ---
def angle_difference(angle1, angle2):
    # ... (unverändert) ...
    a1 = angle1 % 360
    a2 = angle2 % 360
    diff = a2 - a1
    if diff > 180: diff -= 360
    elif diff <= -180: diff += 360
    return diff

# --- KERNFUNKTION: go_to_position (bleibt gleich) ---
def go_to_position(bot_player, target_pos, angle_tolerance, distance_tolerance,
                   screen_width, screen_height, tribune_height):
    # ... (unverändert) ...
    bot_to_target_vec = target_pos - bot_player.pos
    distance_to_target = bot_to_target_vec.length()

    if distance_to_target < distance_tolerance:
        return False

    if bot_to_target_vec.length_squared() < 1e-6:
        return False

    try:
        target_angle = pygame.Vector2(1, 0).angle_to(bot_to_target_vec)
    except ValueError:
        return False

    current_angle = bot_player.angle
    angle_diff = angle_difference(current_angle, target_angle)

    if abs(angle_diff) < angle_tolerance:
        return True
    else:
        return False

# --- HAUPTFUNKTION ---
def get_bot_decision(bot_player, ball, opponent_goal_line_x,
                     screen_width, screen_height, player_radius, ball_radius, tribune_height,
                     dt):
    global _bot_current_mode, _bot_mode_timer

    _bot_mode_timer += dt
    # Die Logik für den Wechsel bleibt gleich, nur die Dauer-Konstanten und der Startmodus sind anders
    if _bot_current_mode == "DEFENSE": # Bot ist im Defense Modus
        if _bot_mode_timer >= BOT_DEFENSE_DURATION: # Zeit für Defense abgelaufen?
            _bot_current_mode = "ATTACK"
            _bot_mode_timer = 0.0
            print(f"BOT LOGIC: Wechsel zu ATTACK Modus (Zeit: {time.time():.1f})")
    elif _bot_current_mode == "ATTACK": # Bot ist im Attack Modus
        if _bot_mode_timer >= BOT_ATTACK_DURATION: # Zeit für Attack abgelaufen?
            _bot_current_mode = "DEFENSE"
            _bot_mode_timer = 0.0
            print(f"BOT LOGIC: Wechsel zu DEFENSE Modus (Zeit: {time.time():.1f})")

    target_pos = pygame.Vector2(0,0)
    current_angle_tolerance = BOT_GOTO_ANGLE_TOLERANCE
    current_distance_tolerance = BOT_GOTO_DISTANCE_TOLERANCE

    if _bot_current_mode == "DEFENSE":
        # ... (Defense Logik bleibt unverändert) ...
        own_goal_line_x = screen_width - 10
        field_height_playable = screen_height - 2 * tribune_height
        own_goal_center_y = tribune_height + field_height_playable / 2
        
        defense_target_x = own_goal_line_x - BOT_DEFENSE_X_LINE_OFFSET
        defense_target_y = ball.pos.y
        defense_target_y = max(own_goal_center_y - BOT_DEFENSE_MAX_Y_DEVIATION_FROM_GOAL_CENTER,
                               min(defense_target_y, own_goal_center_y + BOT_DEFENSE_MAX_Y_DEVIATION_FROM_GOAL_CENTER))
        target_pos = pygame.Vector2(defense_target_x, defense_target_y)

    elif _bot_current_mode == "ATTACK":
        # ... (Attack Logik bleibt unverändert) ...
        opponent_goal_center_y = tribune_height + (screen_height - 2 * tribune_height) / 2
        opponent_goal_pos = pygame.Vector2(opponent_goal_line_x, opponent_goal_center_y)

        bot_to_ball_vec = ball.pos - bot_player.pos
        dist_bot_to_ball = bot_to_ball_vec.length()

        vec_ball_to_opponent_goal = opponent_goal_pos - ball.pos
        
        if vec_ball_to_opponent_goal.length_squared() > 0:
            dir_to_opponent_goal = vec_ball_to_opponent_goal.normalize()
        else:
            dir_to_opponent_goal = pygame.Vector2(-1, 0) if opponent_goal_line_x < screen_width / 2 else pygame.Vector2(1,0)

        kick_reach = player_radius + ball_radius

        if dist_bot_to_ball < kick_reach * 1.2:
            target_pos = ball.pos + dir_to_opponent_goal * (ball_radius + player_radius * 0.5)
            current_angle_tolerance = BOT_ATTACK_KICK_ANGLE_TOLERANCE
            current_distance_tolerance = player_radius * 0.5
        elif dist_bot_to_ball < BOT_ATTACK_MIN_DIST_TO_BALL_FOR_TARGET_BEHIND * 2 :
            target_pos = ball.pos
            current_angle_tolerance = BOT_ATTACK_KICK_ANGLE_TOLERANCE
        else:
            target_pos = ball.pos + dir_to_opponent_goal * (player_radius * BOT_ATTACK_TARGET_DEPTH_FACTOR + ball_radius)
            
    # --- Gemeinsame Logik: Ziel an Spielfeldgrenzen anpassen ---
    # ... (bleibt unverändert) ...
    min_y = tribune_height + player_radius
    max_y = screen_height - tribune_height - player_radius
    min_x = player_radius
    max_x = screen_width - player_radius

    target_pos.x = max(min_x, min(target_pos.x, max_x))
    target_pos.y = max(min_y, min(target_pos.y, max_y))

    sprint_decision = go_to_position(bot_player, target_pos,
                                     current_angle_tolerance,
                                     current_distance_tolerance,
                                     screen_width, screen_height, tribune_height)
    return sprint_decision

# --- Funktion zum Zurücksetzen des Bot-Zustands ---
def reset_bot_state():
    global _bot_current_mode, _bot_mode_timer
    _bot_current_mode = "ATTACK"  # <<<<<<< HIER AUCH ÄNDERN: Reset setzt jetzt in ATTACK Modus zurück
    _bot_mode_timer = 0.0
    print("BOT LOGIC: Interner Zustand auf ATTACK zurückgesetzt.")