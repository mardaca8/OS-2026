# Virtuali ir reali mašina

Martynas Masionis, Artūras Kovtun

Paleidimas: `python main.py` (reikia Python 3 su tkinter).

## Failai

- `memory.py` – atmintis (žodis 4 baitai, blokas 16 žodžių)
- `cpu.py` – procesorius: registrai, komandų vykdymas, pertraukimai, puslapių transliacija, RI / XC / IRET
- `devices.py` – kietasis diskas, klaviatūra, ekranas, kanalų įrenginys
- `supervisor.py` – valdymo programa (paprasta OS): pertraukimų apdorojimas, programos krovimas į atmintį
- `machine.py` – reali mašina, sujungianti visas dalis
- `gui.py`, `main.py` – vartotojo sąsaja
- `programos/` – pavyzdinės programos (SKAI, MAXI, KALK, FAKT, ZENK)

## Naudojimas

- `RUN SKAI` – OS užkrauna programą ir sustoja prieš pirmą komandą
- **Žingsnis (F10)** – vienas žingsnis (VM komanda arba OS darbas po pertraukimo)
- **Vykdyti (F5)** – vykdyti iki pabaigos arba kol programa lauks įvedimo
- įvedus skaičių, jis atiduodamas programai, kuri laukia GN
- `SET R 5`, `SET IC 85`, `MEM 06 100` – keisti registrus ir atmintį
- `DIR`, `HELP`

## Pakeitimai, palyginus su projektu

- OS dar nemultiprograminė, todėl kanalas perduoda bloką iš karto.
- Paleidusi kitą programą (RN), programa laukia, kol ši baigs darbą.
- Rašant programas į diską pašalinami komentarai.
