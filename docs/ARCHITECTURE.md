# Architektura

## Przepływ danych

```text
plik .log/.csv
     |
     v
read_logs() -> lista błędnych rekordów
     |
     v
DataFrame: timestamp, level, message, source_line
     |
     v
filter_events()
     |
     +--> summarize() --------> statystyki
     |
     +--> detect_anomalies() -> alerty
     |
     v
terminal / JSON / CSV / PNG
```

`main()` w `src/log_analyzer/cli.py` odczytuje argumenty, wywołuje kolejne etapy
analizy i obsługuje błędy. Parser, statystyki i detektor działają niezależnie
od interfejsu CLI, co pozwala testować je osobno i wykorzystać w innych interfejsach.

## Parsowanie

`read_logs()` wybiera sposób odczytu według rozszerzenia. Dla `.log`
wyrażenie regularne wydziela datę, poziom i komunikat. CSV obsługuje moduł
`csv`, który rozumie cudzysłowy i przecinki wewnątrz komunikatów.

`_record()` sprawdza poziom i komunikat, a `parse_timestamp()` normalizuje datę
do UTC. Datom bez strefy przypisywane jest UTC. Daty z podanym przesunięciem
są przeliczane na UTC z zachowaniem momentu zdarzenia.

Wynik to `ParseResult`: ramka pandas i lista `ParseIssue` z numerami wierszy
oraz powodami odrzucenia rekordów. Lista trafia do pola `input.issues` w raporcie
JSON. Opcja `--strict` przerywa analizę, jeśli wejście zawiera błędne rekordy.

## Filtry i statystyki

`filter_events()` buduje maskę: serię wartości prawda/fałsz odpowiadających
wierszom. Operator `&` łączy warunki. Zwracana jest kopia wybranych wierszy.

`value_counts()` liczy wystąpienia poziomów i komunikatów.
`resample()` grupuje oś czasu w przedziały. Dzięki temu również godzina bez
zdarzeń ma wynik zero. `ERROR` oraz `CRITICAL` składają się na wspólną serię błędów.

Filtry są stosowane przed obliczaniem statystyk i wykrywaniem anomalii.
Przykładowo `--level ERROR --contains database` ogranicza również historię
detektora do błędów zawierających tekst `database`.

## Wykrywanie anomalii

Konfigurację przechowuje `DetectorConfig`, czyli dataclass z domyślnymi progami.
`detect_anomalies()` dzieli zdarzenia na okna i rozpatruje każde kolejno.

Dla okna z 20 błędami, poprzedzonego trzema oknami po jednym błędzie:

```text
historia = [1, 1, 1]
średnia = 1
odchylenie = 0
próg = max(10, 3 × 1, 1 + 3 × 0) = 10
20 >= 10 -> alert error_spike
```

Obecne okno nie może wejść do historii: podwyższyłoby próg, z którym samo jest
porównywane. Test `test_baseline_excludes_current_and_future_windows` sprawdza
także, że dopisanie przyszłych logów nie zmienia wcześniejszego alertu.

Próg logowań jest niezależny od historii. Natomiast alert skoku błędów i alert
aktywności mogą wystąpić jednocześnie. W danych demonstracyjnych o 13:00 jest
41 błędów i 52 zdarzenia ogółem — oba warunki są spełnione.

`--login-threshold` ustawia próg nieudanych logowań. W przykładzie wartość 30
wyłącza alert dla 25 nieudanych prób. `--window-minutes` zmienia długość okna;
liczba okien historii pozostaje stała, więc zmienia się też jej zakres czasowy.

## Raportowanie i testy

JSON zapisuje zagnieżdżone statystyki, ustawienia i wyjaśnienia. CSV lepiej
nadaje się do tabel, dlatego eksport tworzy osobne pliki zdarzeń,
podsumowania i alertów. Wykres korzysta z tych samych przedziałów czasowych
co detektor, żeby wyniki dało się zestawić.

Testy sprawdzają zachowanie programu na kontrolowanych danych. Szczególnie
istotne są granice przedziałów, puste dane, błędne wejście i brak wpływu
przyszłych obserwacji na wcześniejsze decyzje.

## Decyzje projektowe

- **pandas:** filtrowanie, grupowanie i operacje na osi czasu są wykonywane na
  jednej ramce danych. Ograniczeniem jest przechowywanie całego wejścia w pamięci.
- **Reguły statystyczne:** każdy alert ma możliwy do odtworzenia próg i nie wymaga
  trenowania modelu. Reguły nie uwzględniają sezonowości ani kontekstu zdarzeń.
- **Wspólna strefa UTC:** pozwala porównywać wpisy z różnymi przesunięciami czasu
  i jednoznacznie przypisywać je do okien.
- **Stałe okna:** upraszczają agregację i porównanie wyników z wykresem. Seria
  zdarzeń na granicy okna może zostać podzielona na dwa przedziały.
- **Oddzielenie logiki od CLI:** umożliwia dodanie API bez przenoszenia parsowania
  i detekcji do warstwy HTTP.
