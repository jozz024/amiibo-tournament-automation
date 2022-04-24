# amiibo-tournament-automation

Run automated amiibo tournaments for SSBU.
To be used in conjunction with [match_end](https://github.com/jozz024/match_end).
This requires you have ran joycontrol at least once, so make sure to do that before doing this

## Features
- Automatic amiibo loading
- Automatic menu traversing
- Automatic score reporting
- Automatic result sending

## Installation
- Install dependencies  
```bash
sudo apt install python3-dbus libhidapi-hidraw0 libbluetooth-dev bluez
```
  Python:
  Note that pip here _has_ to be run as root, as otherwise the packages are not available to the root user.
```bash
sudo pip3 install aioconsole hid crc8 nextcord pychallonge
```

- setup bluetooth
  - [I shouldn't have to say this, but] make sure you have a working Bluetooth adapter\
  If you are running inside a VM, the PC might but not the VM. Check for a controller using `bluetoothctl show` or `bluetoothctl list`. Also a good indicator it the actual os reporting to not have bluetooth anymore.
  - disable SDP [only necessary when pairing]\
  change the `ExecStart` parameter in `/lib/systemd/system/bluetooth.service` to `ExecStart=/usr/lib/bluetooth/bluetoothd -C -P sap,input,avrcp`.\
  This is to remove the additional reported features as the switch only looks for a controller.\
  This also breaks all other Bluetooth gadgets, as this also disabled the needed drivers.
  - disable input plugin [experimental alternative to above when not pairing]\
  When not pairing, you can get away with only disabling the `input` plugin, only breaking bluetooth-input devices on your PC. Do so by changing `ExecStart` to `ExecStart=/usr/lib/bluetooth/bluetoothd -C -P input` instead.
  - Restart bluetooth-deamon to apply the changes:
  ```bash
    sudo systemctl daemon-reload
    sudo systemctl restart bluetooth.service
  ```
  - see [Issue #4](https://github.com/Poohl/joycontrol/issues/4) if despite that the switch doesn't connect or disconnects randomly.


## Tournament Scripts
- These are files required to do the automation.
- there are 9 files you have to make:
  ```
  start_game: this file starts the game and brings you to the main menu. you want it to press the home button, 2 A button presses to start the game, sleep for as long as it takes to get to lifelight from boot, and then 2 more A button presses to advance to the main menu

  smash_menu: this is the script that advances you to the character select screen. its basicallly just 3 A button presses spaced out differently depending on the time it takes to get to the next menu from that menu

  smash_menu_after_match: this is the same concept as smash menu, but it removes the first A button press because you dont need once you exit the amiibo save screen.

  load_fp1: this loads the first amiibo after you get to the css. it consists of one down input (held for a bit to get all the way down there), and 2 A button inputs to get to the amiibo scan menu

  load_fp2: this loads the second amiibo. it consists of a right input, and 1 a input to get to the amiibo scan menu

  start_match: literally just the plus button

  on_match_end: gets us from the win screen to the stats page, so 2 A presses.

  after_match: this one is the longest file of them all, it takes us from the stats page to the menu before rule select. it consists of: 2 A button inputs, a B input held for as long as it takes to exit the menu, 2 B button presses, a Right button press, and an A button press

  exit_to_home_and_close_game: this one exits the game. it consists of 1 Home button press, 1 x button press, and one A button press.```

- these files should be formatted as follows:
  ```Button:Length to be held in ms```

- an example:
  ```
  Left:2000
  :4000
  ```

- this would have the left button be held for 2 seconds, and then no input for 4 seconds

## To use the script:
- Put the amiibo bin files from submissionapp in the `tourbins` folder.
- start it
```bash
sudo python3 tourrun.py
```
- If you don't have a config.json present, it will make one and prompt you to fill it out on boot.

- Afterwards, it will ask you for the tournament url (the last part of the url, so if it was `challonge.com/amiibos`, it would be `amiibos`)

- After that, the tournament will be running!

## Issues
- Some bluetooth adapters seem to cause disconnects for reasons unknown, try to use an usb adapter or a raspi instead.
- Incompatibility with Bluetooth "input" plugin requires it to be disabled (along with the others), see [Issue #8](https://github.com/mart1nro/joycontrol/issues/8)
- The reconnect doesn't ever connect, `bluetoothctl` shows the connection constantly turning on and off. This means the switch tries initial pairing, you have to unpair the switch and try without the `-r` option again.
- ...

## Thanks
- Special thanks to https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering for reverse engineering of the joycon protocol
- Thanks to the growing number of contributers and users

## Resources

[Nintendo_Switch_Reverse_Engineering](https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering)

[console_pairing_session](https://github.com/timmeh87/switchnotes/blob/master/console_pairing_session)

[Hardware Issues thread](https://github.com/Poohl/joycontrol/issues/4)
