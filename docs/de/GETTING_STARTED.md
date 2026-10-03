# Erste Schritte

[Dokumentation](README.md) · [English](../GETTING_STARTED.md) · [العربية](../ar/GETTING_STARTED.md)

**0.2.0 alpha:** Eine vollständige Neuinstallation und eine Laufzeitsitzung anhand dieser Anleitung wurden für diese Version noch nicht verifiziert. Die Quellcode-Builds wurden geprüft; das ist eine andere Aussage.

## Voraussetzungen

| Komponente | Anforderung |
|---|---|
| Python | CPython 3.12; eine virtuelle Umgebung im Projekt verwenden |
| Node.js | 24.x; zum erneuten Bauen des Frontends erforderlich |
| Git | Zum Klonen und zur Nachverfolgung des Quellcode-Stands |
| Browser | Lokaler Browser für die Loopback-Oberfläche |
| Docker | Nur für LAB-/PILOT-Erfassung: lokale Linux-x64-Engine; PILOT benötigt zusätzlich einen isolierten Gateway-Modus |

Speichere das Repository auf einem lokalen, beschreibbaren Dateisystem. Lege dort keine Zugangsdaten oder Kundendaten ab. Die Installation von Abhängigkeiten benötigt Zugriff auf Paketquellen; OFFLINE bezeichnet die Prüfung gespeicherter Belege, keinen vom Internet unabhängigen Installer.

## 1. Quellcode vorbereiten

### Windows / PowerShell

```powershell
git clone https://github.com/OmarBajamel/checkout-evidence-monitor.git
cd checkout-evidence-monitor
git switch --detach v0.2.0-alpha.1
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --only-binary=:all: --require-hashes --no-compile -r requirements-dev-win.lock
Set-Location frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
Set-Location ..
.venv/Scripts/python -m build --no-isolation
.venv/Scripts/python -m pip install --no-deps --no-compile dist/checkout_evidence_monitor-0.2.0a1-py3-none-any.whl
```

### Linux / Bash

```bash
git clone https://github.com/OmarBajamel/checkout-evidence-monitor.git
cd checkout-evidence-monitor
git switch --detach v0.2.0-alpha.1
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --require-hashes --no-compile -r requirements-dev-linux.lock
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
cd ..
.venv/bin/python -m build --no-isolation
.venv/bin/python -m pip install --no-deps --no-compile dist/checkout_evidence_monitor-0.2.0a1-py3-none-any.whl
```

Diese Befehle installieren Abhängigkeiten und bauen den Quellcode. Sie starten CEM nicht. Die Installation auf anderen Systemen ist nicht verifiziert. Umgehe keine fehlenden Hashes oder nicht unterstützten Wheels. Wer das Quellcode-ZIP verwendet, kann es entpacken und beim Schritt zum Erstellen der virtuellen Umgebung beginnen.

## 2. Eine OFFLINE-Demo ausdrücklich starten

Führe die folgenden Befehle nur aus, wenn du die lokale Ausführung dieses vorbereiteten Quellcode-Stands autorisieren möchtest. Im unveränderten öffentlichen Repository dokumentiert der Befehl die Absicht des lokalen Betreibers. Er ist weder eine signierte Autorisierung noch eine Erlaubnis, einen Shop aufzurufen.

PowerShell:

```powershell
.venv/Scripts/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile OFFLINE
$env:CEM_TEST_SESSION=(Resolve-Path .cem-private/test-session.json).Path
.venv/Scripts/cem ui --demo
```

Bash:

```bash
.venv/bin/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile OFFLINE
export CEM_TEST_SESSION="$PWD/.cem-private/test-session.json"
.venv/bin/cem ui --demo
```

Öffne den ausgegebenen Loopback-Startlink innerhalb von 60 Sekunden. Er ist nur einmal verwendbar und darf nicht weitergegeben werden. Die Demo verwendet eigens erstellte synthetische Datensätze und einen separaten schreibgeschützten Datenspeicher. Eine Quellcode-Änderung macht die Laufzeitsitzung ungültig; beende sie und erneuere sie bewusst. Den Server beendest du mit Strg+C.

Für eine leere, beschreibbare lokale Arbeitsoberfläche verwendest du denselben Befehl ohne `--demo`. Das Öffnen startet keine Erfassung. Neue Ziele werden pausiert gespeichert; operative Aktionen erfordern den ausdrücklich gestarteten und autorisierten Runner.

## 3. Eine Prüfung nachvollziehen

Wähle in Assessments unterschiedliche Referenz- und Vergleichsdatensätze. Öffne Changes, prüfe eine Ressource auf beiden Seiten und folge ihrem Evidence-Link. Journey zeigt erreichte Zustände und fehlende Abdeckung. In der Demo sind Schreibvorgänge für Prüfentscheidungen deaktiviert. Verwende für einen vollständigen Prüf-/Exportablauf eigene, angemessen bereinigte Datensätze in einem beschreibbaren Speicher.

## 4. Erfassung separat freigeben

- **Synthetisches LAB:** Befolge die englische [LAB-Anleitung](../RUNBOOK.md#isolated-linux-lab). Erforderlich sind eine ausdrückliche OFFLINE_AND_LAB-Sitzung, lokales Docker und eine neue Autorisierung für die synthetische Umgebung.
- **Experimenteller PILOT:** Lies die englischen Hinweise zum [PILOT-Ablauf](../PILOT_QUICKSTART.md) und zu den [Sicherheitsgrenzen](../PILOT_SECURITY.md). Zusätzlich erforderlich sind die ausdrückliche Annahme dieser Grenzen sowie die tatsächliche Berechtigung für exakte Origins, Aktionen und ein kurzes Zeitfenster. Verwende keinen fremden Shop ohne entsprechende Erlaubnis.
- **Tests:** Die Freigabe der Demo erlaubt keine Remote-CI-Ausführung. Der Repository-Workflow wird nur manuell gestartet und hat eigene Eingaben für Absicht und Quellcode-Stand.

## Fehlerbehebung

| Symptom | Prüfen |
|---|---|
| TEST_APPROVAL_REQUIRED | Richtiges Profil, aktuellen Quellcode und gültige Sitzung verwenden; die Schutzprüfung nicht entfernen |
| Leere oder veraltete Browsersitzung | CEM beenden und einen neuen Startlink erzeugen; Bearer-Zugangsdaten werden bewusst nur im Arbeitsspeicher gehalten |
| RUNNER_OFFLINE | Die normale Oberfläche startet den PILOT-Worker nicht; die separate PILOT-Anleitung lesen |
| GRANT_EXPIRED | Erfassung stoppen und die tatsächliche, begrenzte Berechtigung erneuern, bevor die Konfiguration erneuert wird |
| PILOT_IMAGE_REQUIRED | Das Image muss zum vorbereiteten Quellcode passen; nur im Rahmen eines autorisierten PILOT-Vorhabens neu bauen |
| ISOLATION_MISMATCH / CLEANUP_UNCONFIRMED | Neue Arbeit stoppen und der Wiederherstellungsanleitung folgen; Sandbox- oder Netzwerkkontrollen niemals deaktivieren |
| Fehlendes Wheel für eine Abhängigkeit | Python, Betriebssystem und Architektur mit der exakten Lockdatei abgleichen; die Inkompatibilität melden, ohne Hashes zu entfernen |

Es gibt keine zugesagte Support-Reaktionszeit oder universelle Plattformkompatibilität. Nenne in einer bereinigten Fehlermeldung die Version, das Profil, das Betriebssystem und den stabilen Fehlercode.
