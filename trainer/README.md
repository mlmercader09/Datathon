# Entrenador adaptatiu Cangur

L'estudiant resol problemes de M3Kang en una web servida per la placa.

- **Si encerta:** ✓ a la matriu LED i un problema semblant **un nivell més amunt**.
- **Si falla:** ✗, una **pista** (un problema semblant més fàcil, ja resolt) i un problema semblant **un nivell més avall**.

No fa servir el model de llenguatge, així que cada pas triga menys d'un segon. El progrés es guarda en un SQLite a la placa i no surt d'allà.

## Com fa servir M3Kang

| Què | Per a què |
| --- | --- |
| `level` | Triar la dificultat del següent problema |
| Embeddings (`data/index.db`) | Trobar problemes semblants (el mateix tema) per a la pista i el següent problema |
| Traduccions (mateix `id`) | L'estudiant ho veu en català; la cerca es fa amb el text anglès |

Si no hi ha `data/index.db` (per exemple, en un portàtil), la semblança es calcula amb TF-IDF sobre el text anglès. És menys bona, però serveix per desenvolupar.

## Fitxers

| Fitxer | Què fa |
| --- | --- |
| `bank.py` | Carrega els problemes, n'agrupa les traduccions i busca els semblants |
| `trainer.py` | La lògica: corregir, pujar o baixar el nivell, triar la pista i el següent problema |
| `led.py` | El que mostra la matriu LED. Ara només ho escriu per pantalla; a App Lab s'ha de connectar al Bridge |
| `server.py` + `index.html` | La web (només la llibreria estàndard de Python, funciona sense internet) |
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
