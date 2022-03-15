'''
Created on March 15, 2019

@author: Alaric
'''

import asyncio

from time import sleep

from joycontrol.controller_state import button_push

class ScriptRunner(object):
    """
    This class is responsible for parsing and running scripts for the Nintendow Switch Controller

    The class needs a controller passed to it on creation. This is the controller the script runner  will use to run the scripts on.
    Regardless of how the script is passed in (string or file), this script runner expects one line per instruction set, with buttons
    to be held comma separated on the left side of a colon, and a number on the right side of the colon to indicate how many milliseconds it should be held for.
    For example:
    A:100
    :100
    Right:1000
    L,R:500

    Would be interpreted as Hold A for 100 ms, hold nothing for 100 ms, hold Right for 1000 ms, then hold L and R for 500 ms.
    """

    def __init__(self, controller_state, is_looping = False):
        self._controller_state = controller_state
        self._is_looping = is_looping

    async def execute_script_string(self, script_string):
        """
        Takes in a script in a string format and executes it
        """
        while True:
            for line in script_string.splitlines():
                if line[:1] == "#":
                    continue
                buttons, wait_time_ms = self._parse_script_line(line)
                time = wait_time_ms / 1000
                if len(buttons) > 0:
                    await button_push(self._controller_state, *buttons, sec=time)
                else:
                    await asyncio.sleep(time)
            if not self._is_looping:
                break

    async def execute_script_file(self, script_file_name):
        """
        Takes in a filename and pulls script data from it to run.
        """

        while True:
            with open(script_file_name) as script:
                for line in script.readlines():
                    if line[:1] == "#":
                        continue
                    buttons, wait_time_ms = self._parse_script_line(line)
                    time = wait_time_ms / 1000
                    if len(buttons) > 0:
                        await button_push(self._controller_state, *buttons, sec=time)
                    else:
                        await asyncio.sleep(time)

            if not self._is_looping:
                break

    @staticmethod
    def _parse_script_line(script):
        """
        Takes in a single line and tries to parse it as documented in the class docs.

        Returns a tuple  with the first value being an array of button strings, and the second value being an
        int of how many milliseconds to wait for the next button press
        """
        print("Parsing %s" % script)
        input_substring = script[0:script.index(':')].strip()
        wait_time_ms = script[(script.index(':')+1):].strip()
        buttons = input_substring.split(",")
        if len(buttons) == 1 and buttons[0] == "":
            buttons = []
        return buttons, int(wait_time_ms)

    @property
    def is_looping(self):
        return self._is_looping

    @is_looping.setter
    def is_looping(self, is_looping):
        self._is_looping = is_looping
