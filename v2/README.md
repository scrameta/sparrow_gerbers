# Atari Falcon rev2 ("Sparrow") — clean up

The CADSTAR files were previous converted to gerber by a contractor for
cziech (user on Atari forum).

This is an attempt to correct a few errors and replace missing silkscreen.

## All layers

There were some spurious 1 mil lines. These were removed/cleaned up using the remove_spurious_1mil.py script.

## The plane layers (L2 PWR, L5 GND)

These were originally available as two layers each. When doing the conversion the second layer that provides trace boards was missed. This has been recreated using v4 as a reference.

## The bottom silkscreen

After the conversion the bottom silkscreen was a copy of the top silkscreen file. The v4 file has been used with a few corrections to match better.

