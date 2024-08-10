import ujson as json
import mlogging as logging
import os

log = logging.getLogger(__name__)

class config:
    def __init__(self, config_file):
        self.options = []       # text list of options available as class elements
        self.config_file = config_file
        config_data = {}

            # see if the requested config file is present
        try :
            os.stat(config_file)

            # if not, see if the old passwords.json file is present
        except OSError as e:
            if e.errno==errno.ENOENT :
                try :
                        # if so, rename
                    os.rename('passwords.json', config_file)
                    log.info(f'moving passwords.json to {config_file}')
                except :
                    pass

            # attempt to open and read the config file
        try :
            f = open(config_file)
            config_data = json.load(f)
            f.close()
        except OSError as e:
            log.error(f'File {config_file} not found')
        except ValueError:
            log.error('{config_file} does not have a valid json format')

            # we should have at least a hostname in the config file
        if 'hostname' not in config_data:
                # if not, assign a reasonable default name
            config_data['hostname'] = 'PyPower'

            # restructure the config data for easier management and access
        for option in config_data:
            self.options.append(option)
            setattr(self, option, config_data[option])

    def set(self, element, value):
        if element not in self.options:
            self.options.append(element)
        setattr(self, element, value)
        log.info(f'option {element} set to {value}')

    def save(self):
        config_data = {}
        for option in self.options:
            config_data[option] = getattr(self, option)
        print(json.dumps(config_data))
        try:
            with open(self.config_file, mode='w', encoding='utf-8') as f:
                json.dump(config_data, f)
            log.info(f'Configuration saved to {self.config_file}')
        except OSError:
            results = f'Error while writing changes to {self.config_file}'
            log.error(results)

    def show(self):
        results = []
        for option in self.options:
            results.append(f' {option}: {getattr(self, option)}')
        return results

