# Plan: KI-Anrufer im BBS

Wenn ein KI-Key hinterlegt ist, kann man nicht nur mit dem SysOp chatten, sondern
auch mit anderen "Anrufern", die gerade online sind. Jeder Anrufer ist eine
KI-generierte Persona, fest in den 1980ern verankert.

## Feature-Umfang

- **`w` (WHO)** listet die aktuell eingewaehlten User im klassischen BBS-Stil:
  Nummer, Node, Handle, Baudrate, Idle-Zeit, aktuelle Aktion.
- **Personas werden per KI generiert und persistent gespeichert.** Der Pool
  waechst ueber Sessions hinweg bis **maximal 20**: vorhandene werden
  wiederverwendet, neue nur nachgeneriert, solange 20 nicht erreicht sind.
- **Pro Session** wird eine zufaellige Teilmenge (3-8) als "online" markiert,
  mit zufaelligen Nodes, Baudraten und Idle-Zeiten.
- **Jede Persona** hat Handle (szene-typisch, sprachneutral: ZOKK, ACID BURN,
  DR.MODEM), Alter, Ort, Rig (C64, Amiga, 2400-Baud-Modem), Interessen,
  Sprechstil und eine kurze Hintergrundgeschichte. Wissens-Cutoff ca. 1989.
- **`p <n>`** oeffnet einen privaten 1:1-Chat mit dem gelisteten User `n`.
  Loop bis leere Eingabe / `exit` / `quit` / `q`.
- **Chatverlauf ist pro Handle persistent**: trifft man denselben User in einer
  spaeteren Session wieder, erinnert er sich an frueher Gesagtes.
- **Eingehende Chat-Requests**: vor dem Zeichnen des Befehls-Prompts wuerfelt
  der Browser mit kleiner Wahrscheinlichkeit (mit Mindestabstand seit dem
  letzten Mal). Dann erscheint
  `>>> CHAT REQUEST von ZOKK (Node 3) — annehmen? (j/n)`.
- **Ohne KI-Key**: BBS-stilige Fehlermeldung, kein statischer Fallback-Pool.
- **Sprache**: Dialoge in der eingestellten i18n-Sprache, Handles bleiben
  sprachneutral. Alle neuen Texte laufen ueber `t()`.

### Nicht enthalten (Non-Goals)

- Oeffentlicher Multi-User-Chatraum / Teleconference
- Offline-Modus mit handgeschriebenen Personas
- Mail- oder Message-Base-System
- Anklopfen waehrend des Screensavers

## Architektur

Neues Modul **`bbs_browser/users.py`** plus **`bbs_browser/i18n/strings_users.py`**.
Kernklasse `UserBase(term, sysop)`, gehalten am `Browser` — analog zu `sysop`.

### Speicherung

In `state.py`, Sektion `"users"` — **nicht** in `cache.py`. Der Cache hat einen
7-Tage-TTL und LRU-Eviction und wuerde den Pool und die Chatverlaeufe wegwerfen.

```json
"users": {
  "pool":  [ {"handle": "...", "age": 0, "city": "...", "rig": "...",
              "interests": "...", "style": "...", "bio": "..."} ],
  "chats": { "ZOKK": [ {"role": "user", "content": "..."} ] }
}
```

Pool-Cap: 20 Personas. History-Cap: 20 Eintraege pro Handle.

### KI-Anbindung

Ein `client.messages.create`-Call, **kein** `tool_runner` — es werden keine
Tools gebraucht. Bestehende Handles gehen als "nicht nochmal verwenden" in den
Prompt. Tokens laufen ueber das vorhandene `sysop.track()`.

Dafuer neue Methode **`SysOp.converse(system, messages, max_tokens)`**:
schlanker Aufruf ohne Tools, mit `track()`. `run()` bleibt unangetastet, da es
fest an `PERSONA` und `_build_tools()` haengt.

Bewusst ohne Tools: ein 15-jaehriger C64-Freak von 1987 surft nicht im Web.

## Tasks

### 1. Datenmodell & Persistenz

`users.py`, `state.py`

- Persona-Dataclass
- Laden/Speichern der Sektion `"users"`
- Pool-Cap 20 durchsetzen
- History-Trim auf 20 Eintraege pro Handle
- Tolerantes Verhalten bei kaputtem oder leerem State

### 2. KI-Generierung der Personas

- `SysOp.converse()` ergaenzen
- Generator-Prompt: 80er-Verankerung, Wissens-Cutoff ~1989, szene-typische
  Handles, Bio in der i18n-Sprache
- JSON-Parsing mit Fallback bei unbrauchbarer Antwort
- Dedup gegen vorhandene Handles
- Key-Check -> BBS-Fehlermeldung (`NODE LIST UNAVAILABLE`)

### 3. `w` — WHO-Liste

- Session-Auswahl (3-8), einmal pro Session gezogen und im RAM gehalten, damit
  `w` innerhalb einer Session stabil bleibt
- Zufaellige Nodes, Baudraten und Idle-Zeiten
- Ausgabe als Spaltentabelle im BBS-Stil via `term.type_out`
- Registrierung in `navigation.py` und `manual.ALL`

### 4. `p <n>` — Privatchat

- Chat-Loop analog `sysop.chat()`, Ende bei leer / `exit` / `quit` / `q`
- Persona als System-Prompt
- Verlauf pro Handle laden, anhaengen, getrimmt speichern
- Ungueltige Nummer -> Fehlermeldung
- Registrierung in `navigation.py` und `manual.ALL`

### 5. Eingehende Chat-Requests

- `maybe_knock()` in `users.py`: Wahrscheinlichkeit plus Mindestabstand
  (Zeitstempel im RAM)
- Aufruf in `command_loop` **vor** `prompt_with_saver`, damit der Screensaver
  unberuehrt bleibt
- `j` -> Privatchat, alles andere -> kurze Abfuhr-Zeile
- Nur aktiv, wenn Key vorhanden und Pool nicht leer

## Hinweise aus dem Code-Review

1. `sysop.py:50` macht `PERSONA = t("sysop.persona")` auf Modulebene — der Text
   wird beim Import eingefroren. `manual.py` macht dasselbe mit den Kategorien.
   Ein Sprachwechsel zur Laufzeit greift dort also nicht. Das neue Modul folgt
   dem bestehenden Muster, haelt die Prompts aber in Funktionen oder
   Properties, damit es das Problem nicht erbt.

2. Der Chatverlauf pro Handle muss hart begrenzt werden, sonst waechst der
   System-Prompt bei jedem Wiedersehen und die Tokenkosten laufen weg.
