import time

_start_time = time.time()

def uptime() :
    value = time.time() - _start_time
    days = value//(24*60*60)
    value -= days*24*60*60
    hours = value//(60*60)
    value -= hours*60*60
    minutes = value//60
    value -= minutes*60
    seconds = value
    result = []

        # format results, supressing leading 0 days and 0 hours
    if days == 1:
        result.append(f'1 day')
    elif days > 1:
        result.append(f'{days} days')

    if hours == 1:
        result.append(f'1 hour')
    elif hours > 1:
        result.append(f'{hours} hours')
    elif days != 0 :
        result.append(f'0 hours')

    if minutes == 1:
        result.append(f'1 minute')
    else :
        result.append(f'{minutes} minutes')

    return ', '.join(result)

