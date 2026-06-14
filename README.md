# Oneko App

Oneko App puts a tiny animated companion on your desktop. It can follow your
cursor, wander around on its own, sleep, play, eat, and rest on horizontal
lines it finds on the screen.

I made this as a small, cozy desktop app inspired by the classic Oneko cursor
cat. The control window lets you choose a pet, change its size and speed, and
switch between following, resting, and free-roaming modes. You can also
right-click the pet to feed it, play with it, or give it some attention.

## Running from source

You need Python 3.10 or newer. Pillow is optional, but it enables animated
previews and lets the pet detect lines on the screen.

```powershell
python -m pip install -r requirements.txt
python oneko.py
```

Double-click the pet to reopen the controls after hiding them.

## Building the Windows app

Install PyInstaller, then build using the included spec file:

```powershell
python -m pip install pyinstaller
pyinstaller "Oneko App.spec"
```

The built app will appear in the `dist` folder.

## Credits

The pet sprites and preview animations come from the Oneko community and the
Spicetify Oneko project, this code was made by pinki (barak).
