"""Uebersetzungskatalog fuer games.py."""

STRINGS = {
    "games.tty_required": {"de": "Spiele brauchen ein Terminal (TTY)", "en": "Games require a terminal (TTY)"},

    # Menue
    "games.menu_title": {"de": "SPIELHALLE", "en": "ARCADE"},
    "games.menu_subtitle": {"de": "Nummer waehlen, Enter oder q zurueck zum Prompt", "en": "Pick a number, Enter or q returns to the prompt"},
    "games.menu_pong": {"de": "Paddle", "en": "Paddle"},
    "games.menu_tetris": {"de": "Stacker", "en": "Stacker"},
    "games.menu_snake": {"de": "Snake", "en": "Snake"},
    "games.menu_breakout": {"de": "Bricks", "en": "Bricks"},
    "games.menu_dragon": {"de": "Der Uralte Wurm", "en": "The Ancient Wyrm"},
    "games.menu_space": {"de": "Sternenkurier", "en": "Star Courier"},
    "games.menu_record": {"de": "Rekord: {score}", "en": "Record: {score}"},
    "games.unknown_game": {"de": "Kein Spiel namens '{name}'", "en": "No game called '{name}'"},

    # Abspann
    "games.game_over": {"de": "GAME OVER", "en": "GAME OVER"},
    "games.your_score": {"de": "Dein Ergebnis: {score}", "en": "Your score: {score}"},
    "games.new_highscore": {"de": "NEUER REKORD! Eingetragen in die Bestenliste.", "en": "NEW RECORD! Added to the high score table."},
    "games.highscore": {"de": "Bestwert bisher: {score}", "en": "Best so far: {score}"},
    "games.press_enter": {"de": "Enter zurueck zur Spielhalle ", "en": "Enter returns to the arcade "},

    # Paddle
    "games.pong_you": {"de": "DU", "en": "YOU"},
    "games.pong_cpu": {"de": "CPU", "en": "CPU"},
    "games.pong_keys": {"de": "w/s oder Pfeile = Schlaeger   q = Abbruch", "en": "w/s or arrows = paddle   q = quit"},
    "games.pong_result": {"de": "Endstand: {you}:{cpu}", "en": "Final score: {you}:{cpu}"},

    # Stacker
    "games.tetris_title": {"de": "STACKER", "en": "STACKER"},
    "games.tetris_score": {"de": "Punkte: {score}", "en": "Score:  {score}"},
    "games.tetris_lines": {"de": "Reihen: {lines}", "en": "Lines:  {lines}"},
    "games.tetris_level": {"de": "Level:  {level}", "en": "Level:  {level}"},
    "games.tetris_next": {"de": "Naechster Stein:", "en": "Next piece:"},
    "games.tetris_keys_move": {"de": "a/d schieben  w drehen  s schneller", "en": "a/d move  w rotate  s soft drop"},
    "games.tetris_keys_drop": {"de": "Leertaste abwerfen  q Abbruch", "en": "space hard drop  q quit"},

    # Snake
    "games.snake_score": {"de": "Punkte: {score}", "en": "Score: {score}"},
    "games.snake_length": {"de": "Laenge: {length}", "en": "Length: {length}"},
    "games.snake_keys": {"de": "w/a/s/d oder Pfeile = lenken   q = Abbruch", "en": "w/a/s/d or arrows = steer   q = quit"},

    # Bricks
    "games.breakout_score": {"de": "Punkte: {score}", "en": "Score: {score}"},
    "games.breakout_lives": {"de": "Leben: {lives}", "en": "Lives: {lives}"},
    "games.breakout_keys": {"de": "a/d oder Pfeile = Schlaeger   q = Abbruch", "en": "a/d or arrows = paddle   q = quit"},
    "games.breakout_cleared": {"de": "Feld leergeraeumt! Bonus fuer jedes uebrige Leben.", "en": "Field cleared! Bonus for every life left."},
}
