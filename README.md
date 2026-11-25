# TrainLog + DoelTracker

Een mobiele webapp met een Python-server en een SQLite-database. Je houdt hardlooptrainingen bij, kiest een afstandsdoel voor één training en ziet je voortgang in een grafiek. De app begint leeg: er staan geen verzonnen trainingen in.

## Starten

**Makkelijk op je pc:** dubbelklik in Windows Verkenner op **Start TrainLog.bat**. De Python-server start en de app opent automatisch in je standaardbrowser. Laat het terminalvenster open zolang je de app gebruikt. Sluit het venster om de server te stoppen. Je kunt ook met de rechtermuisknop op het bestand een snelkoppeling maken voor je bureaublad.

Je hebt Python 3.10 of nieuwer nodig. Er hoeven geen pakketten geïnstalleerd te worden.

Open een terminal in deze map en voer uit:

```powershell
python app.py
```

Open daarna **http://localhost:8000** in je browser. Laat de terminal open zolang je de app gebruikt. Stop met Ctrl+C.

## Op je telefoon

1. Verbind je telefoon en computer met hetzelfde vertrouwde wifi-netwerk.
2. Start de server met `python app.py --host 0.0.0.0`.
3. Zoek met `ipconfig` het IPv4-adres van je wifi-adapter op.
4. Open op je telefoon `http://DAT-IP-ADRES:8000`, bijvoorbeeld `http://192.168.1.10:8000`.

De firewall kan vragen om Python op je particuliere netwerk toe te staan. Je computer moet aan blijven. Deze eerste versie heeft één gedeeld profiel op de server, zonder accounts. Iedereen die deze server kan bereiken, kan dezelfde trainingen bekijken en aanpassen. Gebruik hem daarom alleen op je eigen vertrouwde netwerk. Vrienden die een eigen profiel willen, starten een eigen kopie.

Dit is een webapp voor mobiel, geen Android- of iOS-installatiebestand. Sommige browsers bieden 'Zet op beginscherm' aan. Volwaardige PWA-installatie op alle apparaten vereist HTTPS en geschikte app-iconen; deze lokale versie garandeert dat niet. De app heeft de Python-server nodig en werkt niet offline.

## AI instellen (optioneel)

Het berekende weekoverzicht werkt altijd zodra er trainingen van de afgelopen zeven dagen zijn. Voor de echte AI-samenvatting heb je een eigen OpenAI API-sleutel en API-tegoed nodig. Zet je sleutel uitsluitend op de server, nooit in JavaScript of in Git.

Stel in dezelfde PowerShell-terminal de variabele `OPENAI_API_KEY` in met je eigen sleutel, en start daarna de server opnieuw. Bijvoorbeeld met `$env:OPENAI_API_KEY = 'jouw-eigen-sleutel'`. Plak de sleutel niet in een chat.

Het standaardmodel is `gpt-4.1-mini`. Met `OPENAI_MODEL` kun je een ander Responses-compatibel model instellen waarvoor je toegang hebt. De AI-knop verstuurt alleen de berekende weektotalen, vergelijking met de vorige zeven dagen en je doel naar OpenAI. Notities worden niet verstuurd. AI-uitvoer wordt als tekst weergegeven. `store: false` wordt meegestuurd.

Implementatie gebaseerd op de [officiële OpenAI Responses API-documentatie](https://developers.openai.com/api/reference/resources/responses/methods/create).

## Waar staat de code?

- `app.py`: Python-server, invoercontrole, database en AI-aanvraag.
- `static/index.html`: schermen en formulieren.
- `static/style.css`: kleuren, vormgeving en telefoonlayout.
- `static/app.js`: knoppen, formulierverzoeken en grafiek.
- `data/trainlog.sqlite3`: je echte gegevens; automatisch aangemaakt en uitgesloten van Git.
- `test_app.py`: tests, met een tijdelijke database en nagebootste AI-dienst.

De database staat op de computer waar Python draait. Sluiten en opnieuw starten wist niets. Maak een reservekopie van het databasebestand terwijl de server uit staat.

## Controleren

```powershell
python -m unittest -v
```

## Zelf leren

Begin in `app.py` bij `number`: herken je de functie, de variabelen en de if? Volg daarna hoe een training via `/api/workouts` wordt gecontroleerd en opgeslagen. Een kleine vervolgoefening: voeg aan het formulier een keuzelijst voor je gevoel na de training toe en sla die ook op.
