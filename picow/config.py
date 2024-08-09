import ujson as json
import mlogging as logging

log = logging.getLogger(__name__)

class config:
    def __init__(self, config_file):
        self.options = []       # text list of options available as class elements
        self.config_file = config_file
        try:
            f = open(config_file)
            config_data = json.load(f)
            f.close()
            for option in config_data:
                self.options.append(option)
                setattr(self, option, config_data[option])

        except OSError:
            log.error(f'File {config_file} not found')
        except ValueError:
            log.error('{config_file} does not have a valid json format')
        finally:
            if 'hostname' not in self.options:
                self.options.append('hostname')
                self.hostname = 'PyPower'

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

