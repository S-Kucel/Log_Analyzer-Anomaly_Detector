# Log Analyzer / Anomaly Detector

Aplikacja CLI w Pythonie do analizy logów i wykrywania nietypowej aktywności.
Generuje statystyki, raporty oraz wykresy. Każdy alert zawiera
przedział czasu, liczbę zdarzeń, próg oraz wyjaśnienie.

**Technologie:** Python 3.10+, pandas, NumPy, matplotlib, pytest.

## Funkcje

- Odczyt plików `.log` i `.csv` w UTF-8, również z BOM.
- Liczba wpisów, rozkład poziomów, najczęstsze komunikaty i błędy, aktywność godzinowa.
- Łączenie filtrów daty, poziomu i fragmentu komunikatu.
- Wykrywanie nieudanych logowań, wzrostu liczby błędów i wzrostu aktywności.
- Raport JSON lub zestaw plików CSV oraz wykres PNG.
- Informacja o błędnych rekordach i tryb `--strict`.
- Przykładowe dane, powtarzalny generator i testy automatyczne.

## Uruchomienie na Windows (PowerShell)

W głównym katalogu projektu:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m log_analyzer examples\server.log --output reports\analysis.json --plot reports\activity.png
```

Nie trzeba aktywować środowiska ani zmieniać polityki wykonywania skryptów PowerShell.
Na Linux/macOS użyj `python3 -m venv .venv` oraz `.venv/bin/python` w kolejnych poleceniach.
Instalacja udostępnia także polecenie `log-analyzer` w katalogu `Scripts` / `bin` środowiska.

Skrócony wynik dla dołączonych danych:

```text
Total events: 425
DEBUG: 0
INFO: 340
WARNING: 37
ERROR: 48
CRITICAL: 0

Most common errors:
     48  Database timeout

Detected anomalies: 4
12:30–12:35  failed_logins    25
13:00–13:05  error_spike      41
13:00–13:05  activity_spike   52
13:30–13:35  activity_spike  112
```

Wszystkie powyższe godziny odnoszą się do 2026-09-30 UTC. Cztery alerty dotyczą
trzech przedziałów: skok błędów zwiększa też łączną liczbę zdarzeń.
Dane są syntetyczne; generator znajduje się w `scripts/generate_demo.py`.

## Format wejścia

Plik `.log`, jeden wpis w wierszu:

```text
2026-09-30 12:00:00 INFO Application started
2026-09-30T12:01:00.125Z [ERROR] Database timeout
2026-09-30T14:02:00+02:00 WARNING Failed login for user demo
```

Plik `.csv`, wymagane nagłówki (w dowolnej kolejności):

```csv
timestamp,level,message
2026-09-30T12:00:00Z,INFO,Application started
2026-09-30T12:01:00Z,ERROR,"Database timeout, retrying"
```

- Poziomy: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`; wielkość liter jest dowolna.
- Aliasy wejściowe `WARN` i `FATAL` są zamieniane na `WARNING` i `CRITICAL`.
- Daty bez strefy są traktowane jako UTC; daty z przesunięciem są przeliczane na UTC.
- W `.log` obsługiwane są ułamki sekund do sześciu cyfr, z kropką lub przecinkiem.
- CSV obsługuje cytowane komunikaty z przecinkami i wieloma wierszami. Dodatkowe kolumny są ignorowane.
- Puste linie są pomijane. Błędne rekordy trafiają do listy problemów.
- Niepoprawny nagłówek lub uszkodzone cytowanie CSV przerywa analizę.
- `source_line` w eksporcie oznacza wiersz pliku; dla wielowierszowego CSV jest to końcowy wiersz rekordu.

## Filtry i eksport

```powershell
# Błędy z całego dnia, zawierające konkretny tekst
.\.venv\Scripts\python.exe -m log_analyzer examples\server.log --since 2026-09-30 --until 2026-09-30 --level ERROR --level CRITICAL --contains "database"

# CSV wejściowy, eksport przefiltrowanych zdarzeń i podsumowania
.\.venv\Scripts\python.exe -m log_analyzer examples\server.csv --level ERROR --output reports\errors.csv

# Własny rozmiar okna i próg logowań, odrzucenie wejścia z błędnymi rekordami
.\.venv\Scripts\python.exe -m log_analyzer examples\server.log --window-minutes 10 --login-threshold 20 --strict

# Wszystkie opcje
.\.venv\Scripts\python.exe -m log_analyzer --help
```

`--since` i `--until` z godziną są włączne. `--until 2026-09-30` obejmuje cały dzień UTC.
`--contains` wyszukuje dosłowny tekst bez rozróżniania wielkości liter, a nie wyrażenie regularne.
Wszystkie statystyki, alerty i wykresy są liczone **po zastosowaniu filtrów**.
Wybranie tylko błędów zmienia więc także znaczenie łącznej aktywności i jej historii.

| Wyjście | Zawartość |
| --- | --- |
| `analysis.json` | Statystyki, aktywność godzinowa, alerty, filtry, konfiguracja reguł i lista odrzuconych rekordów; bez pełnej listy zdarzeń |
| `errors.csv` | Przefiltrowane i posortowane zdarzenia |
| `errors.summary.csv` | Liczba zdarzeń, poziomy, zakres czasu i liczba odrzuconych rekordów |
| `errors.anomalies.csv` | Alerty z progami i wyjaśnieniami |
| `activity.png` | Dwa wykresy: wszystkie zdarzenia oraz `ERROR` + `CRITICAL` w czasie |

Eksport CSV tworzy wszystkie trzy pliki. Istniejące pliki wynikowe są zastępowane;
aplikacja sprawdza, czy któryś z nich nie nadpisałby wejścia.
Kod wyjścia `0` oznacza ukończoną analizę, a `2` błąd argumentów, wejścia lub zapisu.
Pusty plik `.log`, CSV z samym nagłówkiem i puste wyniki filtrowania są obsługiwane.
Plik zawierający wyłącznie błędne rekordy kończy się błędem.

## Jak działają anomalie

Zdarzenia są grupowane w stałe, niepokrywające się okna; domyślnie po 5 minut.
Okna są wyrównane do epoki UTC. Początek jest włączny, koniec wyłączny.

1. **Nieudane logowania:** co najmniej 10 komunikatów pasujących m.in. do
   `failed login`, `login failed`, `failed password`, `authentication failed`,
   `invalid credentials`. Reguła działa także bez wcześniejszej historii.
2. **Skok błędów:** liczba `ERROR` + `CRITICAL` osiąga próg obliczony poniżej;
   minimum wynosi 10.
3. **Skok aktywności:** łączna liczba zdarzeń osiąga ten sam rodzaj progu;
   minimum wynosi 50.

```text
próg = max(minimum, 3 × średnia, średnia + 3 × odchylenie standardowe)
```

Średnia i populacyjne odchylenie standardowe (`ddof=0`) pochodzą z maksymalnie
12 poprzednich okien. Potrzebne są co najmniej 3 wcześniejsze okna.
Puste okna pomiędzy zdarzeniami mają wartość zero. Obecne i przyszłe okna
nie uczestniczą w obliczaniu historii danego alertu. Pozostałe parametry można
zmienić w `DetectorConfig` w module `anomalies.py`.

To heurystyki do wskazywania fragmentów wymagających sprawdzenia. Brak alertu
nie dowodzi braku problemu; alert nie jest potwierdzeniem ataku.

## Testy

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Testy obejmują parser, strefy czasowe, granice dat, literalne filtry tekstu,
statystyki, historię reguł, nakładające się alerty, błędne dane,
eksport JSON/CSV/PNG oraz ochronę pliku wejściowego.
Workflow GitHub Actions uruchamia testy po pushu i przy pull requestach.

## Struktura projektu

```text
src/log_analyzer/
  parser.py       # plik -> DataFrame + lista błędnych rekordów
  analysis.py     # filtry, zliczanie i statystyki
  anomalies.py    # reguły i konfiguracja detektora
  reporting.py    # terminal, JSON, CSV i wykres
  cli.py          # argumenty i połączenie etapów
examples/        # równoważne dane .log i .csv
scripts/         # generator danych przykładowych
tests/           # testy pytest
docs/            # dokumentacja techniczna
```

Przepływ danych i decyzje projektowe opisuje [dokumentacja architektury](docs/ARCHITECTURE.md).

## Ograniczenia i możliwe rozszerzenia

- Obsługiwany jest opisany format; surowe logi nginx, Apache i syslog wymagają osobnych parserów.
- Cały plik jest przechowywany w pamięci. To wersja do analizy małych i średnich plików.
- Reguły nie uwzględniają sezonowości, adresów IP ani unikalnych prób logowania.
  Jeden dopasowany wpis oznacza jedno zliczenie. Wzorce logowania są angielskie.
- Stałe okna mogą podzielić serię zdarzeń na dwa przedziały; niepełne okna na
  początku i końcu pliku mogą też wpływać na porównanie.
- Długie przerwy liczą się jako zera, choć mogą wynikać z braku logów.
  Bardzo duże zakresy wymagające ponad miliona okien są odrzucane.
- FastAPI i modele ML są możliwymi rozszerzeniami tej wersji.
