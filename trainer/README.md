# Entrenador adaptatiu Cangur

L'estudiant resol problemes de M3Kang en una web servida per la placa.

- **Si encerta:** ✓ a la matriu LED i un problema semblant **un nivell més amunt**.
- **Si falla:** ✗, una **pista** (un problema semblant més fàcil, ja resolt) i un problema semblant **un nivell més avall**.

No fa servir el model de llenguatge, així que cada pas triga menys d'un segon. El progrés es guarda en un SQLite a la placa i no surt d'allà.

## Com fa servir M3Kang

| Què | Per a què |
| --- | --- |
| `level` | Triar la dificultat del següent problema |
| Embeddings (`data/trainer_index.db`) | Trobar problemes semblants (el mateix tema) per a la pista i el següent problema |
| Traduccions (mateix `id`) | L'estudiant ho veu en català; la cerca es fa amb el text anglès |

Si no hi ha `data/trainer_index.db` (per exemple, en un portàtil), la semblança es calcula amb TF-IDF sobre el text anglès. És menys bona, però serveix per desenvolupar.

## Fitxers

| Fitxer | Què fa |
| --- | --- |
| `bank.py` | Carrega els problemes, n'agrupa les traduccions i busca els semblants |
| `trainer.py` | La lògica: corregir, pujar o baixar el nivell, triar la pista i el següent problema |
| `led.py` | El que mostra la matriu LED. Ara només ho escriu per pantalla; a App Lab s'ha de connectar al Bridge |
| `server.py` + `index.html` | La web (només la llibreria estàndard de Python, funciona sense internet) |
| `../applab/cangur-trainer/` | L'app d'App Lab: la mateixa web al port 7000 i la matriu LED (✓, ✗ i el nivell) |
| `../applab/install.sh` | Copia l'app, el codi de `trainer/`, les dades i les imatges a `~/ArduinoApps/cangur-trainer` |
| `simulate.py` | Estudiants simulats, per mesurar si el nivell s'ajusta bé |

## Com provar-ho

Des de la carpeta del repositori, amb `data/train.jsonl` i `data/val.jsonl` ja preparats (pas 9):

```bash
python -m trainer.simulate          # estudiants simulats
python -m trainer.server            # la web: http://127.0.0.1:8000
```

A la placa és el mateix, amb `python3`. Afegiu `--host 0.0.0.0` perquè s'hi pugui connectar un altre dispositiu de la mateixa xarxa.

## Què mesurem

- **Temps per pas** (`ms/step`): ha de ser molt per sota d'1 segon.
- **Nivell final dels estudiants simulats**: un estudiant que sap fins al nivell *t* hauria d'acabar oscil·lant entre *t-1* i *t*.
- **Semblança** entre un problema i el següent: indica si es manté el tema.
- **Pistes més fàcils**: quantes pistes són realment d'un nivell més baix.
- A mà, sobre 20 pistes: el problema semblant és realment del mateix tema i més fàcil?

## A la placa

Des de la carpeta del repositori a la placa, amb les dades i les imatges ja copiades (pas 10 i secció *explorer* del README principal) i els serveis dels models engegats (pas 7).

### 1. Els embeddings de tots els problemes (uns 10 minuts, una sola vegada)

L'entrenador necessita l'embedding de **tots** els problemes, també els de validació, i en anglès (bge-small és un model anglès). Per això fa servir un índex propi, `data/trainer_index.db`, diferent del `data/index.db` de `predict.py`:

```bash
cat data/train.jsonl data/val.jsonl > data/all.jsonl
python3 build_index.py --input data/all.jsonl --db data/trainer_index.db --languages eng
```

No feu servir `--only-with-options`: sense OCR, gairebé cap problema té les opcions en text.

### 2. Comprovar-ho

```bash
python3 -m trainer.simulate     # ha de dir "similarity: embeddings from data/trainer_index.db"
```

### 3. L'app d'App Lab (web + matriu LED)

```bash
bash applab/install.sh
arduino-app-cli app start user:cangur-trainer
```

Obriu `http://<ip-de-la-placa>:7000`. Per veure què passa: `arduino-app-cli app logs ~/ArduinoApps/cangur-trainer --all`.

Cada cop que canvieu alguna cosa de `trainer/`, torneu a executar `install.sh` i reinicieu l'app. No editeu les còpies de dins `~/ArduinoApps`.

### Què mostra la matriu

| Moment | Matriu |
| --- | --- |
| Esperant un estudiant | `?` |
| Després de respondre | ✓ o ✗ durant 1,5 segons |
| Sempre que no hi ha ✓ o ✗ | El nivell (0 a 7) en gran, i una barra a la fila de baix que creix amb el nivell |

### Si alguna cosa falla

- **L'app no arrenca:** mireu els logs. Si diu que no troba `train.jsonl`, torneu a executar `install.sh`.
- **No surten les imatges:** comproveu que `data/images` existeix a la placa abans d'executar `install.sh`.
- **Memòria:** App Lab i els dos models comparteixen 3,6 GB. Mireu `free -m` amb tot engegat. L'entrenador no fa servir els models mentre funciona, així que si cal memòria podeu aturar-los (`sudo systemctl stop math-llm`) després de construir l'índex.
