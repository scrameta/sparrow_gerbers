# Atari Falcon rev2 ("Sparrow") — clean up

The CADSTAR files were previous converted to gerber by a contractor for
cziech (user on Atari forum).

This is an attempt to correct a few errors and replace missing silkscreen.

## All layers

There were some spurious 1 mil lines. These were removed/cleaned up using the remove_spurious_1mil.py script.

## The plane layers (L2 PWR, L5 GND)

These were originally available as two layers each. When doing the conversion these two were incorrectly combined.

The pads part of these were recreated using CADSTAR -> Altium -> Kicad -> gerber.
The clearance part was then recreated using both v4 and the corrupt combination. It was not available after the CADSTAR -> Altium step.
The two were then combined properly

## The bottom silkscreen

After the conversion the bottom silkscreen was a copy of the top silkscreen file. 

The file was recreated using CADSTAR -> Altium -> Kicad -> gerber.

