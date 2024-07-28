import sys

# Implement a line buffer to collect keystrokes and handle backspace/delete
_console_command = ''
_csi_state = None
_ESC = '\033'

def process_key(key_value) :
    global _csi_state
    global _console_command
    if _csi_state is not None :
        if _csi_state == '': # == _ESC      # have seen ESC, process second charactor
            if key_value == '[':            # expected value; consume for now
                _csi_state = '['
                return None
            else :                          # unexpected value, process normally
                pass

        elif _csi_state[0] == '[':           # collecting CSI printable charactors
            if key_value.isdigit() :        #  all decimal digits after bracket
                _csi_state += key_value
                return None
            elif key_value == '~':          #  terminator of the digits (and CSI sequence)
                if _csi_state == '[3':       #     VT-100 delete key
                    key_value = '\b'        #         remap to backspace code
                    _csi_state = None
                else :
                    pass
            else :                          # unexpected value
                pass

        # if _csi_state has a value at this point CSI processing was aborted
        if _csi_state is not None:
            text = '<ESC>' + _csi_state
            _console_command += text
            sys.stdout.write(text)
            _csi_state = None

        # CSI lead-in charactor detection
    if key_value == _ESC:
        _csi_state = ''  # indicates that ESC has been received
        return None

        # backspace handling
    if key_value==chr(127) or key_value=='\b':
        if len(_console_command) > 0 :
            _console_command = _console_command[:-1]
            sys.stdout.write('\b \b')
        return None

        # process the command here? Maybe return the command?
    if key_value == '\n':
        sys.stdout.write('\n')
        command = _console_command
        _console_command = ''
        return command

        # no special processing - just collect and echo
    _console_command += key_value
    sys.stdout.write(key_value)
    return None
